"""Email service for notifications."""
import logging
from typing import List, Optional
from flask import render_template_string
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""
    
    def __init__(self, mail: Optional[Mail] = None):
        """
        Initialize email service.
        
        Args:
            mail: Flask-Mail instance
        """
        self.mail = mail
    
    def send_email(
        self,
        subject: str,
        recipients: List[str],
        body: str,
        html: Optional[str] = None,
        sender: Optional[str] = None
    ):
        """
        Send email.
        
        Args:
            subject: Email subject
            recipients: List of recipient emails
            body: Plain text body
            html: HTML body
            sender: Sender email
        """
        if not self.mail:
            logger.warning("Email service not configured")
            return
        
        try:
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=body,
                html=html,
                sender=sender
            )
            self.mail.send(msg)
            logger.info(f"Email sent to {recipients}")
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
    
    def send_verification_email(self, user_email: str, verification_link: str):
        """Send email verification."""
        subject = "Verify Your ResearchHub Account"
        body = f"Click this link to verify your account: {verification_link}"
        html = f"""
        <h2>Welcome to ResearchHub Pro!</h2>
        <p>Please verify your email address by clicking the link below:</p>
        <p><a href="{verification_link}">Verify Email</a></p>
        """
        self.send_email(subject, [user_email], body, html)
    
    def send_password_reset_email(self, user_email: str, reset_link: str):
        """Send password reset email."""
        subject = "Reset Your ResearchHub Password"
        body = f"Click this link to reset your password: {reset_link}"
        html = f"""
        <h2>Password Reset Request</h2>
        <p>Click the link below to reset your password:</p>
        <p><a href="{reset_link}">Reset Password</a></p>
        <p>If you didn't request this, please ignore this email.</p>
        """
        self.send_email(subject, [user_email], body, html)
    
    def send_research_alert(self, user_email: str, query: str, new_results: int):
        """Send research alert for saved searches."""
        subject = f"New Research Results: {query}"
        body = f"Found {new_results} new results for your saved search: {query}"
        html = f"""
        <h2>New Research Results Available</h2>
        <p>Your saved search "<strong>{query}</strong>" has {new_results} new results.</p>
        <p><a href="https://researchhub.com/dashboard">View Results</a></p>
        """
        self.send_email(subject, [user_email], body, html)
