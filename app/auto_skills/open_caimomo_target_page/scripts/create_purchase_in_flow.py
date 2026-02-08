from langchain_core.tools import tool
from typing import Dict, Any, Optional, List
import os
import time
from urllib.parse import urlparse

from app.skills.playwright_skill.scripts import _playwright_core as core


@tool
def create_caimomo_purchase_in_bill(
    url: str = "https://v2.caimomo.com/ScmWeb/SCM/Bill/PurchaseIn.aspx",
    headless: bool = False,
    supplier: str = "",
    department: str = "",
    materials: Optional[List[Dict[str, Any]]] = None,
    save_and_continue: bool = False
) -> Dict[str, Any]:
    """
    在采购入库页面执行新增流程：选择部门/供应商 -> 添加物料 -> 编辑数量与单价 -> 保存
    """
    result = {
        "success": False,
        "message": "",
        "steps": [],
        "error": None,
        "screenshot": None
    }
    page = None
    try:
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
        extension_dir = os.getenv("PLAYWRIGHT_EXTENSION_DIR") or core._get_default_extension_dir()
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)

        page, err = core._ensure_page(
            headless=headless, user_data_dir=user_data_dir, extension_dir=extension_dir
        )
        if err:
            result["error"] = err
            result["steps"].append(f"页面初始化失败: {err}")
            return result

        auto_load_cookie = (os.getenv("PLAYWRIGHT_AUTO_LOAD_COOKIES") or "1").strip().lower()
        if auto_load_cookie in ("1", "true", "yes", "on"):
            hostname = urlparse(url).hostname
            if hostname:
                core._apply_cookies_for_domain(hostname, base_url=url)
                result["steps"].append(f"已加载{hostname}的cookie")

        result["steps"].append(f"导航到采购入库页面: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            body_text = page.text_content("body") or ""
            if ("没有访问" in body_text) or ("权限" in body_text):
                raise Exception("页面提示无访问权限，请先登录或通过菜单进入后再执行新增流程")
        except Exception:
            pass
        page.wait_for_selector("#add", timeout=15000, state="visible")
        page.wait_for_function("() => window.$ && window.$.fn && window.$.fn.datagrid")

        result["steps"].append("点击新增按钮")
        page.click("#add")
        page.wait_for_selector("#updateModal", timeout=8000, state="visible")

        department = (department or "").strip()
        supplier = (supplier or "").strip()
        if not department:
            raise Exception("入库部门不能为空")
        if not supplier:
            raise Exception("供应商不能为空")

        result["steps"].append("等待部门与供应商选项加载")
        page.wait_for_function(
            """() => {
                const dept = document.querySelector("#dept");
                if (!dept) return false;
                const options = dept.querySelectorAll("option");
                return options && options.length > 1;
            }""",
            timeout=15000,
        )
        page.wait_for_function(
            """() => {
                if (!window.$) return false;
                const options = window.$("#supplier option");
                return options && options.length > 1;
            }""",
            timeout=15000,
        )

        result["steps"].append(f"选择入库部门: {department}")
        dept_selected = page.evaluate(
            """
            (deptName) => {
                const select = document.querySelector("#dept");
                if (!select) return false;
                const options = Array.from(select.options || []);
                const matched = options.find((opt) => (opt.textContent || "").trim().includes(deptName));
                if (!matched) return false;
                select.value = matched.value;
                select.dispatchEvent(new Event("change", { bubbles: true }));
                return true;
            }
            """,
            department,
        )
        if not dept_selected:
            raise Exception(f"未找到入库部门: {department}")

        result["steps"].append(f"选择供应商: {supplier}")
        supplier_selected = page.evaluate(
            """
            (supplierName) => {
                const $select = window.$("#supplier");
                const options = $select.find("option");
                let target = null;
                options.each(function () {
                    const text = (this.textContent || "").trim();
                    if (text && text.includes(supplierName)) {
                        target = this.value;
                        return false;
                    }
                });
                if (!target) return false;
                $select.val(target);
                $select.selectpicker("refresh");
                $select.trigger("change");
                return true;
            }
            """,
            supplier,
        )
        if not supplier_selected:
            raise Exception(f"未找到供应商: {supplier}")

        result["steps"].append("打开添加物料弹窗")
        page.click("#addGoods")
        page.wait_for_selector("#commonModal", timeout=8000, state="visible")
        page.wait_for_function(
            """() => {
                return !!(window.global && window.global.materialData && window.global.materialData.length);
            }""",
            timeout=15000,
        )

        materials = materials or []
        if not materials:
            raise Exception("物料列表不能为空")

        for index, item in enumerate(materials):
            keyword = (item.get("keyword") or item.get("name") or item.get("goods_name") or item.get("goods_no") or "").strip()
            if not keyword:
                raise Exception("物料项缺少 keyword/name/goods_name/goods_no")

            result["steps"].append(f"筛选物料: {keyword}")
            page.evaluate(
                """
                (kw) => {
                    const input = document.querySelector("#txt2");
                    if (!input) return false;
                    input.value = kw;
                    const event = window.$.Event("keyup");
                    event.keyCode = 65;
                    window.$(input).trigger(event);
                    return true;
                }
                """,
                keyword,
            )

            page.wait_for_function(
                """() => {
                    try {
                        const rows = window.$("#goodsDg").datagrid("getRows") || [];
                        return rows.length > 0;
                    } catch (e) {
                        return false;
                    }
                }""",
                timeout=15000,
            )

            matched_index = page.evaluate(
                """
                (kw) => {
                    const rows = window.$("#goodsDg").datagrid("getRows") || [];
                    for (let i = 0; i < rows.length; i++) {
                        const r = rows[i] || {};
                        const name = (r.GoodsName || "");
                        const no = (r.GoodsNo || "");
                        const quick = (r.GoodsQuickCode || "");
                        if (name.includes(kw) || no.includes(kw) || quick.includes(kw)) {
                            window.$("#goodsDg").datagrid("checkRow", i);
                            return i;
                        }
                    }
                    return -1;
                }
                """,
                keyword,
            )
            if matched_index < 0:
                raise Exception(f"未找到物料: {keyword}")

            is_last = index == len(materials) - 1
            if is_last:
                result["steps"].append("确认选中物料并关闭弹窗")
                page.evaluate("() => { try { window.addGoods && window.addGoods(false, 0); } catch(e){} }")
                page.wait_for_selector("#commonModal", timeout=8000, state="hidden")
            else:
                result["steps"].append("添加物料并继续")
                page.evaluate("() => { try { window.addGoods && window.addGoods(false, 1); } catch(e){} }")
                page.wait_for_selector("#commonModal", timeout=8000, state="visible")

        result["steps"].append("等待物料加载到入库明细表")
        page.wait_for_function(
            """() => {
                try {
                    const rows = window.$("#updMaterialTable").datagrid("getRows");
                    return rows && rows.length > 0;
                } catch (e) {
                    return false;
                }
            }""",
            timeout=10000,
        )

        for item in materials:
            keyword = (item.get("keyword") or item.get("name") or item.get("goods_name") or item.get("goods_no") or "").strip()
            quantity = item.get("quantity")
            unit_price = item.get("unit_price")
            total_price = item.get("total_price")
            pieces = item.get("pieces")
            memo = item.get("memo")
            result["steps"].append(f"填写入库明细: {keyword}")
            update_ok = page.evaluate(
                """
                (payload) => {
                    const dg = window.$("#updMaterialTable");
                    const rows = dg.datagrid("getRows") || [];
                    let idx = -1;
                    for (let i = 0; i < rows.length; i++) {
                        const r = rows[i] || {};
                        const name = (r.GoodsName || "");
                        const no = (r.GoodsNo || "");
                        if (name.includes(payload.keyword) || no.includes(payload.keyword)) {
                            idx = i;
                            break;
                        }
                    }
                    if (idx < 0) return false;
                    dg.datagrid("selectRow", idx);
                    dg.datagrid("beginEdit", idx);
                    const setNumber = (field, value) => {
                        if (value === undefined || value === null || value === "") return;
                        const editor = dg.datagrid("getEditor", { index: idx, field });
                        if (!editor) return;
                        if (window.$(editor.target).numberbox) {
                            window.$(editor.target).numberbox("setValue", value);
                        } else {
                            window.$(editor.target).val(value);
                        }
                    };
                    const setText = (field, value) => {
                        if (value === undefined || value === null) return;
                        const editor = dg.datagrid("getEditor", { index: idx, field });
                        if (!editor) return;
                        window.$(editor.target).val(value);
                    };
                    setNumber("Quantity2", payload.quantity);
                    setNumber("UnitPrice2", payload.unit_price);
                    setNumber("TotalPrice", payload.total_price);
                    setNumber("Pieces", payload.pieces);
                    setText("Memo", payload.memo);
                    dg.datagrid("endEdit", idx);
                    return true;
                }
                """,
                {
                    "keyword": keyword,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "pieces": pieces,
                    "memo": memo,
                },
            )
            if not update_ok:
                raise Exception(f"未在入库明细表找到物料: {keyword}")

        if save_and_continue:
            result["steps"].append("点击保存并继续")
            page.click("#updatingBtnContinue")
        else:
            result["steps"].append("点击保存")
            page.click("#updatingBtn")

        result["success"] = True
        result["message"] = "采购入库新增流程执行完成"
        result["steps"].append("操作完成")
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["message"] = f"操作失败: {str(e)[:80]}"
        result["steps"].append(f"错误详情: {str(e)}")
        if page:
            try:
                screenshot_name = f"caimomo_purchase_in_error_{os.getpid()}_{int(time.time())}.png"
                page.screenshot(path=screenshot_name, full_page=True)
                result["screenshot"] = screenshot_name
                result["steps"].append(f"错误截图已保存: {screenshot_name}")
            except Exception as se:
                result["steps"].append(f"截图失败: {str(se)[:50]}")
    return result

