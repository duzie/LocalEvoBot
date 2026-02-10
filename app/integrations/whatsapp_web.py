import os
import json
import time
import threading
import queue
from web.backend.shared import shared
from app.integrations import heartbeat

WHATSAPP_PREFIX = "__WA__:"
# Global state for deduplication
# Map title -> Set of processed message keys (limit size?)
# To keep it simple and bounded, we can use a dict of deque or list
from collections import deque
_seen = {} # Format: { title: deque([key1, key2, ...], maxlen=50) }

# --- Worker Thread Infrastructure ---
_cmd_queue = queue.Queue()
_worker_thread = None

def _worker_loop():
    while True:
        try:
            func, args, kwargs, result_queue = _cmd_queue.get(timeout=1.0)
        except queue.Empty:
            continue
            
        try:
            res = func(*args, **kwargs)
            if result_queue:
                result_queue.put(("ok", res))
        except Exception as e:
            if result_queue:
                result_queue.put(("error", e))
        finally:
            _cmd_queue.task_done()

def _ensure_worker():
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="WhatsAppWorker")
        _worker_thread.start()

def _run_in_worker(func, *args, **kwargs):
    _ensure_worker()
    q = queue.Queue()
    _cmd_queue.put((func, args, kwargs, q))
    status, res = q.get()
    if status == "error":
        raise res
    return res

# --- Internal Logic (Runs in Worker Thread) ---

def _user_data_dir():
    value = os.getenv("WHATSAPP_USER_DATA_DIR")
    if value:
        return value
    base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..")))
    data_dir = os.path.join(base_dir, "app", "data", "whatsapp_user")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def _get_page_internal():
    try:
        from app.skills.playwright_skill.scripts import _playwright_core as core
    except Exception as e:
        shared.set_error(f"Playwright 不可用: {e}")
        return None
    
    # Ensure we are calling this from the worker thread context
    page, err = core._ensure_page(headless=False, user_data_dir=_user_data_dir(), extension_dir=None)
    if err:
        shared.set_error(str(err))
        return None
    try:
        if not page.url or "web.whatsapp.com" not in page.url:
            page.goto("https://web.whatsapp.com", timeout=30000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
    except Exception as e:
        shared.set_error(f"打开 WhatsApp Web 失败: {e}")
        return None
    return page

def _is_ready_internal(page):
    try:
        return bool(page.evaluate("() => !!document.querySelector('#pane-side')"))
    except Exception:
        return False

def _open_login_internal():
    page = _get_page_internal()
    if not page:
        return {"ok": False, "error": shared.last_error or "打开失败"}
    ready = _is_ready_internal(page)
    return {"ok": True, "ready": ready, "url": page.url}

def _dump_dom_internal():
    page = _get_page_internal()
    if not page:
        return None, shared.last_error or "打开失败"
    try:
        html = page.content()
        return html, None
    except Exception as e:
        return None, f"获取页面结构失败: {e}"

def _current_chat_title_internal(page):
    try:
        return page.evaluate("""
        () => {
            const header = document.querySelector('header');
            if (header) {
                const el = header.querySelector('span[title]');
                if (el && el.getAttribute('title')) return el.getAttribute('title');
                const el2 = header.querySelector('[data-testid="conversation-info-header-chat-title"], [data-testid="conversation-info-header-chat-title"] span');
                if (el2) return (el2.textContent || '').trim();
                // Fallback for obfuscated headers: look for the largest text element in header
                const spans = Array.from(header.querySelectorAll('span[dir="auto"]'));
                if (spans.length > 0) return spans[0].textContent;
            }
            const sel = document.querySelector('#pane-side [role="row"][aria-selected="true"], #pane-side [role="listitem"][aria-selected="true"]');
            if (sel) {
                const t = sel.querySelector('span[title], div[title], [aria-label]');
                if (t) return (t.getAttribute('title') || t.getAttribute('aria-label') || t.textContent || '').trim();
                // Fallback: get first meaningful text in the selected row
                return (sel.textContent || '').split('\\n')[0].trim();
            }
            return '';
        }
        """) or ""
    except Exception:
        return ""

def _select_chat_internal(page, title: str):
    # Strategy 1: Playwright Locators (Most Reliable)
    try:
        pane = page.locator("#pane-side")
        
        # 1a. Exact title match on span/div
        # Note: WhatsApp titles are often in title attribute or aria-label
        t1 = pane.locator(f'span[title="{title}"], div[title="{title}"], [aria-label="{title}"]').first
        if t1.is_visible():
            t1.click()
            # Wait for main panel to load this chat
            try:
                page.wait_for_selector("header", timeout=2000)
            except:
                pass
            return True
            
        # 1b. Text match (if title attribute is missing)
        # Use a more specific selector to avoid matching time/message preview
        t2 = pane.locator(f'div[role="row"] span[dir="auto"][title="{title}"]').first
        if t2.is_visible():
            t2.click()
            return True
            
        t3 = pane.get_by_text(title, exact=True).first
        if t3.is_visible():
            t3.click()
            return True
            
    except Exception as e:
        print(f"[WhatsApp] Locator selection failed: {e}")

    # Strategy 2: JS Fallback (For complex/obfuscated DOMs)
    script = """
    (name) => {
        const pane = document.querySelector('#pane-side');
        if (!pane) return false;
        // Support both role="listitem" (old) and role="row" (new/grid)
        const items = Array.from(pane.querySelectorAll('div[role="listitem"], div[role="row"]'));
        const match = (item) => {
            const el = item.querySelector('span[title], div[title], [aria-label]');
            if (el) {
                const t = (el.getAttribute('title') || el.getAttribute('aria-label') || el.textContent || '').trim();
                if (t === name) return true;
            }
            // Fallback: check raw text content if title/label missing
            const raw = (item.textContent || '').trim();
            return raw.includes(name);
        };
        const item = items.find(match);
        if (!item) return false;
        
        // Simulate native click
        const mouseDown = new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window });
        const mouseUp = new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window });
        const click = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
        
        item.dispatchEvent(mouseDown);
        item.dispatchEvent(mouseUp);
        item.dispatchEvent(click);
        
        // Also try standard click method
        item.click();
        return true;
    }
    """
    try:
        ok = bool(page.evaluate(script, title))
        if ok:
            # Wait a bit for transition
            try:
                page.wait_for_timeout(500)
                # Verify if we actually switched? 
                # For now just wait for message list container
                # page.wait_for_selector("div.message-in, div[class*='message-in']", timeout=3000)
            except Exception:
                pass
        return ok
    except Exception as e:
        print(f"[WhatsApp] JS selection failed: {e}")
        return False

def _send_text_internal(page, title: str, text: str):
    if not text:
        return False
    
    # 1. Ensure we are on the right chat
    current = _current_chat_title_internal(page)
    if current != title:
        print(f"[WhatsApp] Switching to {title} for reply...")
        ok = _select_chat_internal(page, title)
        if not ok:
            print(f"[WhatsApp] Failed to switch to {title}")
            return False
        time.sleep(0.5)
        
    try:
        # 2. Find input box
        # Try locator first
        box = page.locator('footer div[contenteditable="true"][role="textbox"]').first
        if not box.is_visible():
             box = page.locator('footer div[contenteditable="true"]').first
             
        if not box.is_visible():
            # Fallback to JS selector
            input_ok = page.evaluate("() => { const box = document.querySelector('footer div[contenteditable=\"true\"]'); if (!box) return false; box.click(); return true; }")
            if not input_ok:
                print("[WhatsApp] Input box not found")
                return False
        else:
            box.click()
            
        # 3. Type message
        # We must handle newlines carefully. typing '\n' triggers 'Enter' which sends the message.
        # We want 'Shift+Enter' for newlines.
        print(f"[WhatsApp] Sending to {title}: {text[:20]}...")
        
        parts = text.split('\n')
        for i, part in enumerate(parts):
            if part:
                page.keyboard.type(part)
            
            # If not the last part, insert a newline via Shift+Enter
            if i < len(parts) - 1:
                page.keyboard.down("Shift")
                page.keyboard.press("Enter")
                page.keyboard.up("Shift")
                time.sleep(0.05) # Brief pause for stability
        
        time.sleep(0.5) 
        
        # 4. Send
        page.keyboard.press("Enter")
        
        return True
    except Exception as e:
        print(f"[WhatsApp] Send failed: {e}")
        return False

def _dump_ax_tree_internal():
    page = _get_page_internal()
    if not page:
        return "Page not initialized"
    try:
        # Get the main chat panel's accessibility tree
        main = page.locator("#main")
        if not main.is_visible():
            return "Main panel not visible"
            
        snapshot = page.accessibility.snapshot(root=main.element_handle())
        return json.dumps(snapshot, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error dumping AX tree: {e}"

def dump_ax():
    try:
        return _run_in_worker(_dump_ax_tree_internal)
    except Exception as e:
        return str(e)

def _send_reply_internal(sender: str, text: str):
    try:
        page = _get_page_internal()
        if page and _is_ready_internal(page):
            return _send_text_internal(page, sender, text)
        return False
    except Exception as e:
        shared.set_error(f"WhatsApp 回复失败: {e}")
        return False

def _list_unread_internal(page, limit: int = 5):
    script = """
    (limit) => {
        const pane = document.querySelector('#pane-side');
        if (!pane) return [];
        // Support both role="listitem" (old) and role="row" (new/grid)
        const items = Array.from(pane.querySelectorAll('div[role="listitem"], div[role="row"]'));
        const res = [];
        const getTitle = (item) => {
            const titleEl = item.querySelector('span[title], div[title], [aria-label]');
            const t = titleEl ? (titleEl.getAttribute('title') || titleEl.getAttribute('aria-label') || titleEl.textContent) : '';
            return (t || '').trim();
        };
        for (const item of items) {
            const title = getTitle(item);
            if (!title) continue;
            
            // STRICT UNREAD CHECK & COUNT EXTRACTION:
            // Look for the unread badge (green bubble with number)
            const unreadBadge = item.querySelector('span[aria-label*="unread"], span[aria-label*="未读"], span[class*="_1pJ9J"]');
            
            // Try to parse count from badge text or aria-label
            let count = 0;
            if (unreadBadge) {
                const text = unreadBadge.textContent || '';
                const match = text.match(/\\d+/);
                if (match) count = parseInt(match[0], 10);
                else count = 1; // Badge exists but no number visible? Assume 1.
            } else {
                // Check item aria-label for "X unread messages"
                const itemLabel = item.getAttribute('aria-label') || '';
                const match = itemLabel.match(/(\\d+)\\s+(unread|未读)/i);
                if (match) {
                    count = parseInt(match[1], 10);
                }
            }
            
            if (count > 0) {
                res.push({ title, count });
                if (res.length >= limit) break;
            }
        }
        return res;
    }
    """
    try:
        return page.evaluate(script, limit)
    except Exception:
        return None

def _list_candidates_internal(page, limit: int = 8):
    script = """
    (limit) => {
        const pane = document.querySelector('#pane-side');
        if (!pane) return [];
        const items = Array.from(pane.querySelectorAll('div[role="listitem"]'));
        const res = [];
        const getTitle = (item) => {
            const titleEl = item.querySelector('span[title], div[title], [aria-label]');
            const t = titleEl ? (titleEl.getAttribute('title') || titleEl.getAttribute('aria-label') || titleEl.textContent) : '';
            return (t || '').trim();
        };
        for (const item of items) {
            const title = getTitle(item);
            if (!title) continue;
            res.push({ title });
            if (res.length >= limit) break;
        }
        return res;
    }
    """
    try:
        return page.evaluate(script, limit) or []
    except Exception:
        return []

def _last_incoming_internal(page):
    # Strategy: Semantic Parsing via AX Tree (ARIA Labels)
    # This is more robust than CSS classes because it relies on accessibility attributes
    # which WhatsApp maintains for screen readers.
    script = """
    () => {
        const main = document.querySelector('#main');
        if (!main) return null;
        
        // 1. Get all message rows (AX Role: row)
        const rows = Array.from(main.querySelectorAll('div[role="row"]'));
        if (rows.length === 0) {
            // Fallback to class-based if role not found (older versions)
            const msgs = main.querySelectorAll('div.message-in, div.message-out');
            if (msgs.length > 0) return { _fallback: true }; 
            return null;
        }
        
        // 2. Iterate backwards to find the last INCOMING message
        for (let i = rows.length - 1; i >= 0; i--) {
            const row = rows[i];
            
            // 3. Semantic Analysis via ARIA
            // WhatsApp usually puts the sender info in aria-label of the inner container
            // e.g. aria-label="Message from 小冬瓜: Hello..." or "Message sent by you: ..."
            const labeledEl = row.querySelector('[aria-label]');
            let label = labeledEl ? labeledEl.getAttribute('aria-label') : '';
            
            // Heuristic A: Check for "Sent by you" (Outgoing)
            // Note: This string depends on language! "Message sent by you" (EN), "你发送的消息" (CN)
            // But we can also check the standard class as a strong signal.
            const isOutgoingClass = row.classList.contains('message-out') || row.querySelector('.message-out');
            
            if (isOutgoingClass) continue;
            
            // Heuristic B: If label explicitly says "Sent by you" (just in case class is missing)
            # if (label.includes("Sent by you") || label.includes("你发送")) continue;

            // 4. Extract Content Semantically
            let text = '';
            
            // Try to find the actual message text node (often has 'selectable-text' class)
            const textNode = row.querySelector('span.selectable-text span, .selectable-text, span[dir="auto"]');
            if (textNode) {
                text = textNode.textContent;
            } else {
                // Fallback: Use the label but strip metadata if possible?
                // Or just raw text
                text = row.innerText || row.textContent;
                // Cleanup timestamp (often at the end)
                text = text.split('\\n')[0]; 
            }
            text = (text || '').trim();
            if (!text) continue;
            
            // 5. Extract Metadata
            const dataId = row.getAttribute('data-id') || (row.querySelector('[data-id]') ? row.querySelector('[data-id]').getAttribute('data-id') : '');
            
            // 6. Semantic Result
            return {
                text: text,
                dataId: dataId,
                sender: label ? label.split(':')[0] : 'Unknown', // Rough guess
                is_incoming: true
            };
        }
        
        // Fallback for non-role structures
        return { _fallback: true };
    }
    """
    try:
        res = page.evaluate(script)
        if res and res.get("_fallback"):
            # Execute legacy logic if semantic parsing didn't return a clear result
            # (Reusing the robust CSS logic we wrote earlier)
            return page.evaluate("""
            () => {
                const main = document.querySelector('#main');
                if (!main) return null;
                const all = Array.from(main.querySelectorAll('div.message-in, div.message-out'));
                for (let i = all.length - 1; i >= 0; i--) {
                    const el = all[i];
                    if (el.classList.contains('message-out') || el.matches('div[class*="message-out"]')) continue;
                    let text = '';
                    const textNode = el.querySelector('span.selectable-text span, .selectable-text, span[dir="auto"]');
                    if (textNode) text = textNode.textContent || '';
                    else text = (el.innerText || el.textContent || '').split('\\n')[0];
                    text = text.trim();
                    if (!text) continue;
                    const dataId = el.getAttribute('data-id') || (el.querySelector('[data-id]') ? el.querySelector('[data-id]').getAttribute('data-id') : '');
                    return { text, dataId };
                }
                return null;
            }
            """)
        return res
    except Exception:
        return None

def _ensure_observer_internal(page):
    script = """
    () => {
        try {
            if (!window.__WA_INBOUND__) {
                window.__WA_INBOUND__ = [];
            }
            if (!window.__WA_OBS) {
                const obs = new MutationObserver((mutations) => {
                    const pushMsg = (el) => {
                        // 1. Semantic Check via ARIA
                        const label = el.querySelector('[aria-label]') ? el.querySelector('[aria-label]').getAttribute('aria-label') : '';
                        
                        // Ignore outgoing messages
                        // Heuristic: Check for "Sent by you" in label OR specific class
                        if (el.classList.contains('message-out') || el.matches('.message-out')) return;
                        # if (label && (label.includes("Sent by you") || label.includes("你发送"))) return;

                        let text = '';
                        const textNode = el.querySelector('span.selectable-text span, .selectable-text, span[dir="auto"]');
                        if (textNode) {
                            text = textNode.textContent;
                        } else {
                            text = (el.innerText || el.textContent || '').split('\\n')[0];
                        }
                        text = (text || '').trim();
                        if (!text) return;
                        
                        const dataId = el.getAttribute('data-id') || (el.querySelector('[data-id]') ? el.querySelector('[data-id]').getAttribute('data-id') : '');
                        
                        // Get current chat title from header
                        // Try various selectors for the header title
                        const headerTitleEl = document.querySelector('header span[title], header div[role="button"] span[dir="auto"]');
                        const title = headerTitleEl ? (headerTitleEl.getAttribute('title') || headerTitleEl.innerText) : '';
                        
                        window.__WA_INBOUND__.push({
                            title: title,
                            text: text,
                            dataId: dataId,
                            timestamp: Date.now()
                        });
                    };
                    
                    for (const m of mutations) {
                        for (const node of Array.from(m.addedNodes)) {
                            if (node && node.nodeType === 1) {
                                const el = node;
                                // Check for message row
                                if (el.getAttribute('role') === 'row' || el.classList.contains('message-in')) {
                                    pushMsg(el);
                                } else {
                                    // Check children (sometimes a container is added)
                                    const candidates = el.querySelectorAll('div[role="row"], div.message-in');
                                    candidates.forEach(c => pushMsg(c));
                                }
                            }
                        }
                    }
                });
                
                // Observe #main for child additions
                const main = document.querySelector('#main');
                if (main) {
                    obs.observe(main, { childList: true, subtree: true });
                    window.__WA_OBS = obs;
                } else {
                    // Retry later if main not found
                    // But usually _tick calls this when ready
                }
            }
            return true;
        } catch {
            return false;
        }
    }
    """
    try:
        return bool(page.evaluate(script))
    except Exception:
        return False

def _drain_inbound_internal(page, limit: int = 10):
    script = """
    (limit) => {
        try {
            const list = window.__WA_INBOUND__ || [];
            const out = list.splice(0, Math.max(1, Number(limit) || 10));
            return out;
        } catch {
            return [];
        }
    }
    """
    try:
        return page.evaluate(script, limit) or []
    except Exception:
        return []

def _enqueue_message(sender: str, text: str):
    payload = {"source": "whatsapp", "sender": sender, "text": text}
    shared.put_input(WHATSAPP_PREFIX + json.dumps(payload, ensure_ascii=False))

def _fetch_recent_messages_internal(page, limit: int = 1):
    # Fetch last N incoming messages
    # DEBUG: Returning debug info in specific fields to diagnose why messages are skipped
    script = """
    (limit) => {
        const main = document.querySelector('#main');
        if (!main) return [{debug: "No main panel"}];
        
        // Expand selectors to be safe
        const rows = Array.from(main.querySelectorAll('div[role="row"], div.message-in, div.message-out'));
        if (rows.length === 0) {
             return [{debug: "No rows found"}];
        }
        
        const res = [];
        const debug_log = [];
        
        // Iterate backwards
        let count = 0;
        // Limit debug log size
        const debug_limit = 10; 
        
        for (let i = rows.length - 1; i >= 0; i--) {
            const row = rows[i];
            
            // Extract basic info for debug
            const isOutgoing = row.classList.contains('message-out') || row.querySelector('.message-out') || row.classList.contains('message-out-focus');
            const labeledEl = row.querySelector('[aria-label]');
            let label = labeledEl ? labeledEl.getAttribute('aria-label') : '';
            
            // Refined Text Extraction Logic
            let text = '';
            
            // Helper to check if text is just a timestamp (e.g. "4:41 PM", "16:30", "昨天")
            // This prevents the agent from reading the time as the message
            const isTimestamp = (t) => {
                if (!t) return false;
                t = t.trim();
                // Common time formats
                const timeRegex = /^\d{1,2}:\d{2}(\s?[AaPp][Mm])?$/; 
                if (timeRegex.test(t)) return true;
                // Short date strings often found in message rows
                if (['昨天', 'Today', 'Yesterday'].includes(t)) return true;
                return false;
            };

            // Strategy 1: Look for standard message text container (most reliable)
            const textNode = row.querySelector('span.selectable-text span, .selectable-text');
            if (textNode) {
                text = textNode.textContent;
            }
            
            // Strategy 2: Fallback to any span with dir="auto" BUT filter out timestamps
            if (!text) {
                 const candidates = Array.from(row.querySelectorAll('span[dir="auto"]'));
                 for (const cand of candidates) {
                     const t = cand.textContent || '';
                     if (t && !isTimestamp(t)) {
                         text = t;
                         break; // Found a likely message candidate
                     }
                 }
            }

            // Strategy 3: Last resort - innerText lines, excluding timestamp-looking lines
            if (!text) {
                const lines = (row.innerText || row.textContent || '').split('\\n');
                for (const line of lines) {
                    const t = line.trim();
                    if (t && !isTimestamp(t)) {
                         text = t;
                         break;
                    }
                }
            }
            
            text = (text || '').trim();
            
            const dataId = row.getAttribute('data-id') || (row.querySelector('[data-id]') ? row.querySelector('[data-id]').getAttribute('data-id') : '');
            
            if (debug_log.length < debug_limit) {
                 debug_log.push(`Idx:${i} Out:${isOutgoing} Txt:${text.substring(0, 10)}... ID:${dataId}`);
            }

            if (isOutgoing) continue; // Skip outgoing
            if (!text) continue; // Skip empty
            
            res.unshift({
                text: text,
                dataId: dataId,
                sender: label ? label.split(':')[0] : 'Unknown',
                timestamp: Date.now()
            });
            
            count++;
            if (count >= limit) break;
        }
        
        // Attach debug log to the first item or create a dummy item if empty
        if (res.length > 0) {
            res[0]._debug = debug_log;
        } else {
            return [{_debug: debug_log, _fallback: true}]; // Signal to Python that we found nothing but here is why
        }
        
        return res;
    }
    """
    try:
        return page.evaluate(script, limit)
    except Exception as e:
        print(f"[WhatsApp] Fetch error: {e}")
        return []

def _process_chat_internal(page, title: str, is_unread: bool = False, unread_count: int = 1):
    if not title:
        return
        
    # If unread, we fetch exactly 'unread_count' messages.
    # If not unread (monitoring open chat), we fetch just 1 (last).
    limit = unread_count if is_unread else 1
    
    msgs = _fetch_recent_messages_internal(page, limit=limit)
    if not msgs:
        return

    # Print Debug Info
    if msgs and isinstance(msgs[0], dict) and msgs[0].get("_debug"):
        print(f"[WhatsApp] Debug Scan for '{title}': {msgs[0]['_debug']}")
        
    # Check for fallback
    if len(msgs) == 1 and msgs[0].get("_fallback"):
        # Legacy single message fetch
        # last_msg = _last_incoming_internal(page)
        # if last_msg:
        #      msgs = [last_msg]
        # else:
        return

    # Process messages in chronological order (they are already sorted by _fetch... unshift)
    for msg in msgs:
        text = str(msg.get("text") or "").strip()
        data_id = str(msg.get("dataId") or "").strip()
        key = data_id or text
        if not text:
            continue
            
        seen_msgs = _seen.get(title)
        
        # If this is the first time we see this chat:
        if seen_msgs is None:
            # Initialize the deque
            seen_msgs = deque(maxlen=50)
            _seen[title] = seen_msgs
            
            # If we are processing UNREAD messages, we accept them all!
            if is_unread:
                 if key not in seen_msgs:
                     seen_msgs.append(key)
                     print(f"[WhatsApp] Processing unread message {unread_count} from '{title}': {text[:20]}...")
                     _enqueue_message(title, text)
            else:
                 # Initial tracking, ignore history
                 # Add ALL fetched messages to seen so we don't process them later
                 if key not in seen_msgs:
                     seen_msgs.append(key)
                 print(f"[WhatsApp] Initialized tracking for '{title}'. Ignoring historical message: {text[:20]}...")
            continue
            
        if key in seen_msgs:
            continue
            
        # Update seen
        seen_msgs.append(key)
        print(f"[WhatsApp] New inbound message: {title}: {text[:20]}...")
        _enqueue_message(title, text)

def _tick_internal():
    page = _get_page_internal()
    if not page:
        return
    if not _is_ready_internal(page):
        return
    
    _ensure_observer_internal(page)
    inbound = _drain_inbound_internal(page, limit=10)
    for entry in inbound:
        try:
            title = str((entry or {}).get("title") or "").strip()
            text = str((entry or {}).get("text") or "").strip()
            data_id = str((entry or {}).get("dataId") or "").strip()
            if not title or not text:
                continue
            key = data_id or text
            seen_msgs = _seen.get(title)
            
            if seen_msgs is None:
                seen_msgs = deque(maxlen=50)
                _seen[title] = seen_msgs
                
            if key in seen_msgs:
                continue
                
            seen_msgs.append(key)
            print(f"[WhatsApp] New inbound message via observer: {title}: {text[:20]}...")
            _enqueue_message(title, text)
        except Exception:
            pass
            
    unread = _list_unread_internal(page, limit=5)
    unread_titles = set()
    if unread:
        unread_titles = {str(u.get('title') or '').strip() for u in unread if u.get('title')}
        unread_counts = {str(u.get('title') or '').strip(): u.get('count', 1) for u in unread if u.get('title')}
        print(f"[WhatsApp] Found {len(unread)} unread chats: {list(unread_counts.items())}")
        
    scan_list = unread
    
    # Critical Fix: Even if no "unread" badges are found (e.g. chat is already open),
    # we MUST check the currently open chat for new messages.
    current_title = _current_chat_title_internal(page)
    if current_title:
        # Check current chat immediately
        # Treat as unread if it was in the unread list
        is_current_unread = current_title in unread_titles
        current_count = unread_counts.get(current_title, 1)
        _process_chat_internal(page, current_title, is_unread=is_current_unread, unread_count=current_count)
    
    if not scan_list:
        scan_list = _list_candidates_internal(page, limit=3) # Reduce scan limit
    
    for item in scan_list:
        title = (item or {}).get("title") or ""
        if not title:
            continue
        
        # Only switch if we are not already on it
        current = _current_chat_title_internal(page)
        if current != title:
            ok = _select_chat_internal(page, title)
            if not ok:
                continue
            time.sleep(1.0)
            
        is_item_unread = title in unread_titles
        item_count = unread_counts.get(title, 1)
        _process_chat_internal(page, title, is_unread=is_item_unread, unread_count=item_count)

# --- Public Interface (Thread-Safe Wrappers) ---

def enabled():
    value = os.getenv("WHATSAPP_ENABLE", "0")
    return str(value).strip().lower() in ["1", "true", "yes", "on"]

def poll_interval():
    try:
        return max(0.5, float(os.getenv("WHATSAPP_POLL_INTERVAL", "2")))
    except Exception:
        return 2.0

def open_login():
    try:
        return _run_in_worker(_open_login_internal)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def dump_dom():
    try:
        return _run_in_worker(_dump_dom_internal)
    except Exception as e:
        return None, str(e)

def send_reply(sender: str, text: str):
    try:
        return _run_in_worker(_send_reply_internal, sender, text)
    except Exception:
        return False

def _tick():
    if not enabled():
        return
    try:
        _run_in_worker(_tick_internal)
    except Exception as e:
        shared.set_error(f"WhatsApp 监听失败: {e}")

def start():
    # Initialize worker thread early
    _ensure_worker()
    heartbeat.register_task(
        "whatsapp_web_listener",
        _tick,
        poll_interval,
        enabled=enabled,
        on_error=lambda e: shared.set_error(f"WhatsApp 监听失败: {e}"),
    )
    return True

def parse_payload(raw: str):
    if not raw or not str(raw).startswith(WHATSAPP_PREFIX):
        return None
    text = str(raw)[len(WHATSAPP_PREFIX):].strip()
    try:
        data = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data
