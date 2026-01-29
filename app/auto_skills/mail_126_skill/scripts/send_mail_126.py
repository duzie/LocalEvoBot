from langchain_core.tools import tool
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

@tool
def send_mail_126(
    sender_email: Optional[str] = None,
    sender_password: Optional[str] = None,
    receiver_email: str = None,
    subject: str = None,
    body: str = None,
    attachment_path: Optional[str] = None
) -> dict:
    """
    发送126邮件
    
    Args:
        sender_email: 发件人邮箱（如：your_email@126.com），如果不提供则从环境变量读取
        sender_password: 发件人授权码（不是登录密码），如果不提供则从环境变量读取
        receiver_email: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        attachment_path: 附件路径（可选）
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 从环境变量读取发件人信息（如果参数未提供）
        if sender_email is None:
            sender_email = os.getenv("MAIL_126_SENDER_EMAIL")
            if not sender_email:
                return {
                    "success": False,
                    "message": "发件人邮箱未提供且未在环境变量中设置。请提供sender_email参数或在.env文件中设置MAIL_126_SENDER_EMAIL",
                    "error": "Missing sender_email"
                }
        
        if sender_password is None:
            sender_password = os.getenv("MAIL_126_SENDER_PASSWORD")
            if not sender_password:
                return {
                    "success": False,
                    "message": "发件人密码未提供且未在环境变量中设置。请提供sender_password参数或在.env文件中设置MAIL_126_SENDER_PASSWORD",
                    "error": "Missing sender_password"
                }
        
        # 检查必需参数
        if not receiver_email:
            return {
                "success": False,
                "message": "收件人邮箱不能为空",
                "error": "Missing receiver_email"
            }
        
        if not subject:
            return {
                "success": False,
                "message": "邮件主题不能为空",
                "error": "Missing subject"
            }
        
        if not body:
            return {
                "success": False,
                "message": "邮件正文不能为空",
                "error": "Missing body"
            }
        
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        # 添加正文
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 添加附件（如果有）
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                attachment = MIMEApplication(f.read())
                attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=os.path.basename(attachment_path)
                )
                msg.attach(attachment)
        
        # 连接126邮箱SMTP服务器
        # 126邮箱SMTP服务器：smtp.126.com，端口：25（普通）或465（SSL）
        # 使用SSL连接更安全
        smtp_server = "smtp.126.com"
        smtp_port = 465
        
        # 发送邮件
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return {
            "success": True,
            "message": f"邮件发送成功！发件人：{sender_email}，收件人：{receiver_email}",
            "subject": subject,
            "note": "发件人信息已从环境变量读取" if os.getenv("MAIL_126_SENDER_EMAIL") else "发件人信息由参数提供"
        }
        
    except smtplib.SMTPAuthenticationError as e:
        return {
            "success": False,
            "message": f"认证失败: {str(e)}",
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"发送邮件失败: {str(e)}",
            "error": str(e)
        }