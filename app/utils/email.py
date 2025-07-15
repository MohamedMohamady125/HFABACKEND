# app/utils/email.py - Complete Email Utility Functions

import sendgrid
from sendgrid.helpers.mail import Mail
from app.config import settings
import logging

# Set up logging
logger = logging.getLogger(__name__)

def send_reset_code_email(to_email: str, user_name: str, reset_code: str):
    """
    Send password reset code via email using SendGrid
    
    Args:
        to_email (str): Recipient email address
        user_name (str): User's name for personalization
        reset_code (str): 6-digit reset code
    
    Returns:
        bool: True if email sent successfully
        
    Raises:
        Exception: If email sending fails
    """
    
    # Create the email message
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject="🔐 Your HFA Password Reset Code",
        html_content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Password Reset Code</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 30px;
                    text-align: center;
                    color: white;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                }}
                .content {{
                    padding: 30px;
                }}
                .code-box {{
                    background: linear-gradient(135deg, #f8f9ff 0%, #e8f0ff 100%);
                    border: 2px solid #667eea;
                    border-radius: 12px;
                    padding: 25px;
                    text-align: center;
                    margin: 30px 0;
                    position: relative;
                }}
                .code-box::before {{
                    content: "🔐";
                    position: absolute;
                    top: -15px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: white;
                    padding: 0 10px;
                    font-size: 20px;
                }}
                .code-label {{
                    margin: 0 0 15px 0;
                    font-size: 14px;
                    color: #666;
                    font-weight: 500;
                }}
                .code {{
                    font-size: 36px;
                    font-weight: bold;
                    color: #667eea;
                    letter-spacing: 8px;
                    margin: 0;
                    font-family: 'Courier New', monospace;
                }}
                .info-box {{
                    background: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .info-box strong {{
                    color: #856404;
                }}
                .security-tips {{
                    background: #e8f4fd;
                    border-left: 4px solid #007bff;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .security-tips h3 {{
                    margin: 0 0 10px 0;
                    color: #0056b3;
                    font-size: 16px;
                }}
                .security-tips ul {{
                    margin: 0;
                    padding-left: 20px;
                }}
                .security-tips li {{
                    margin-bottom: 5px;
                    color: #0056b3;
                }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    background: #f8f9fa;
                    border-top: 1px solid #e9ecef;
                    color: #6c757d;
                    font-size: 12px;
                }}
                .button {{
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    margin: 20px 0;
                }}
                @media (max-width: 600px) {{
                    body {{
                        padding: 10px;
                    }}
                    .content {{
                        padding: 20px;
                    }}
                    .code {{
                        font-size: 28px;
                        letter-spacing: 4px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset Code</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">HFA Athletic Management System</p>
                </div>
                
                <div class="content">
                    <p style="font-size: 16px; margin-bottom: 20px;">
                        Hi <strong>{user_name}</strong>,
                    </p>
                    
                    <p style="font-size: 16px; margin-bottom: 20px;">
                        You requested to reset your password for your HFA account. 
                        Use the verification code below in the mobile app to continue with your password reset:
                    </p>
                    
                    <div class="code-box">
                        <p class="code-label">Your Verification Code:</p>
                        <h2 class="code">{reset_code}</h2>
                    </div>
                    
                    <div class="info-box">
                        <strong>⏰ Important:</strong> This code expires in <strong>15 minutes</strong> for your security.
                    </div>
                    
                    <div class="security-tips">
                        <h3>🛡️ Security Tips:</h3>
                        <ul>
                            <li>Never share this code with anyone</li>
                            <li>HFA staff will never ask for this code</li>
                            <li>If you didn't request this reset, ignore this email</li>
                            <li>Use the code only in the official HFA mobile app</li>
                        </ul>
                    </div>
                    
                    <p style="font-size: 14px; color: #666; margin-top: 30px;">
                        If you didn't request this password reset, you can safely ignore this email. 
                        Your account security has not been compromised.
                    </p>
                    
                    <p style="font-size: 14px; color: #666;">
                        Need help? Contact our support team at 
                        <a href="mailto:support@hfa.com" style="color: #667eea;">support@hfa.com</a>
                    </p>
                </div>
                
                <div class="footer">
                    <p>This is an automated message from HFA Athletic Management System.</p>
                    <p>Please do not reply to this email.</p>
                    <p style="margin-top: 10px;">
                        © 2025 HFA Athletic Management. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    )

    try:
        logger.info(f"🔑 Sending reset code email to {to_email}")
        
        # Initialize SendGrid client
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        
        # Send the email
        response = sg.send(message)
        
        # Log success
        logger.info(f"✅ Reset code email sent successfully to {to_email} | Status: {response.status_code}")
        
        # Check if email was sent successfully
        if response.status_code in [200, 201, 202]:
            return True
        else:
            logger.error(f"❌ SendGrid returned non-success status: {response.status_code}")
            raise Exception(f"SendGrid API returned status {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Failed to send reset code email to {to_email}: {str(e)}")
        raise Exception(f"Email sending failed: {str(e)}")

def send_welcome_email(to_email: str, user_name: str, branch_name: str):
    """
    Send welcome email when registration is approved
    
    Args:
        to_email (str): Recipient email address
        user_name (str): User's name
        branch_name (str): Branch they were assigned to
    """
    
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject="🎉 Welcome to HFA - Registration Approved!",
        html_content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Welcome to HFA</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                    padding: 30px;
                    text-align: center;
                    color: white;
                }}
                .content {{
                    padding: 30px;
                }}
                .welcome-box {{
                    background: linear-gradient(135deg, #f8fff9 0%, #e8f5e8 100%);
                    border: 2px solid #28a745;
                    border-radius: 12px;
                    padding: 25px;
                    text-align: center;
                    margin: 20px 0;
                }}
                .branch-info {{
                    background: #e8f4fd;
                    border-left: 4px solid #007bff;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    background: #f8f9fa;
                    border-top: 1px solid #e9ecef;
                    color: #6c757d;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to HFA!</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Your registration has been approved</p>
                </div>
                
                <div class="content">
                    <p style="font-size: 16px;">Hi <strong>{user_name}</strong>,</p>
                    
                    <div class="welcome-box">
                        <h2 style="color: #28a745; margin: 0 0 15px 0;">🏆 Registration Approved!</h2>
                        <p style="margin: 0; font-size: 16px;">
                            Welcome to the HFA Athletic Management family!
                        </p>
                    </div>
                    
                    <p>Great news! Your registration has been reviewed and approved by our coaching staff.</p>
                    
                    <div class="branch-info">
                        <h3 style="margin: 0 0 10px 0; color: #0056b3;">📍 Your Branch Assignment</h3>
                        <p style="margin: 0; font-weight: 600; color: #0056b3; font-size: 16px;">
                            {branch_name}
                        </p>
                    </div>
                    
                    <h3>🚀 What's Next?</h3>
                    <ul>
                        <li>You can now log in to the HFA mobile app using your email and password</li>
                        <li>View your training schedule and attendance</li>
                        <li>Track your progress and measurements</li>
                        <li>Communicate with your coaches</li>
                        <li>Stay updated with branch announcements</li>
                    </ul>
                    
                    <p style="font-size: 14px; color: #666; margin-top: 30px;">
                        If you have any questions, don't hesitate to contact your branch coaches or our support team.
                    </p>
                </div>
                
                <div class="footer">
                    <p>Welcome to HFA Athletic Management System!</p>
                    <p>© 2025 HFA Athletic Management. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
    )

    try:
        logger.info(f"📧 Sending welcome email to {to_email}")
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"✅ Welcome email sent to {to_email} | Status: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send welcome email to {to_email}: {str(e)}")
        return False

def send_registration_notification_email(to_email: str, coach_name: str, athlete_name: str, branch_name: str):
    """
    Send notification email to coaches about new registration requests
    
    Args:
        to_email (str): Coach's email address
        coach_name (str): Coach's name
        athlete_name (str): New athlete's name
        branch_name (str): Branch name
    """
    
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject=f"🔔 New Registration Request - {athlete_name}",
        html_content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Registration Request</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                    padding: 30px;
                    text-align: center;
                    color: white;
                }}
                .content {{
                    padding: 30px;
                }}
                .notification-box {{
                    background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
                    border: 2px solid #ffa000;
                    border-radius: 12px;
                    padding: 25px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    background: #f8f9fa;
                    border-top: 1px solid #e9ecef;
                    color: #6c757d;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔔 New Registration Request</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Action Required</p>
                </div>
                
                <div class="content">
                    <p style="font-size: 16px;">Hi Coach <strong>{coach_name}</strong>,</p>
                    
                    <div class="notification-box">
                        <h3 style="margin: 0 0 15px 0; color: #e65100;">⏰ New Registration Pending</h3>
                        <p style="margin: 0; font-size: 16px;">
                            <strong>{athlete_name}</strong> has submitted a registration request for <strong>{branch_name}</strong>
                        </p>
                    </div>
                    
                    <p>A new athlete has requested to join your branch and needs your approval to access the system.</p>
                    
                    <h3>📱 Next Steps:</h3>
                    <ol>
                        <li>Open the HFA Coach app</li>
                        <li>Go to "Registration Requests"</li>
                        <li>Review {athlete_name}'s application</li>
                        <li>Approve or reject the request</li>
                    </ol>
                    
                    <p style="background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <strong>💡 Tip:</strong> You can review the athlete's information and contact details 
                        before making your approval decision.
                    </p>
                    
                    <p style="font-size: 14px; color: #666;">
                        This notification is sent only to coaches assigned to the {branch_name} branch.
                    </p>
                </div>
                
                <div class="footer">
                    <p>HFA Athletic Management System - Coach Notifications</p>
                    <p>© 2025 HFA Athletic Management. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
    )

    try:
        logger.info(f"🔔 Sending registration notification to coach {to_email}")
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"✅ Registration notification sent to {to_email} | Status: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send registration notification to {to_email}: {str(e)}")
        return False

# Legacy function for backward compatibility
def send_reset_email(to_email: str, token: str):
    """
    Legacy function for token-based password reset (if still needed)
    """
    reset_url = f"https://yourapp.com/reset-password?token={token}"

    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject="🔐 Reset Your HFA Password",
        html_content=f"""
        <p>Hi there,</p>
        <p>You requested to reset your password. Click the link below:</p>
        <a href="{reset_url}">Reset Password</a>
        <p>If you didn't request this, you can ignore this email.</p>
        """
    )

    try:
        logger.info(f"🔑 Sending legacy reset email to {to_email}")
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"✅ Legacy reset email sent to {to_email} | Status: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send legacy reset email: {e}")
        return False