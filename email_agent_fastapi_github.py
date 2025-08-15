#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 15 21:45:44 2025

@author: carousell
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 21:55:57 2025

@author: carousell
"""

# email_agent_api.py
import os
import smtplib
from email.mime.text import MIMEText
from fastapi import FastAPI
from pydantic import BaseModel
from openai import AzureOpenAI

# ====== Azure OpenAI Setup ======
endpoint = ""
deployment = ""
api_version = ""
subscription_key = ""

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

# ====== FastAPI App ======
app = FastAPI(title="Email Writing Agent API")

# ====== Request Body Schema ======
class EmailRequest(BaseModel):
    subject: str
    recipient_name: str
    context: str
    to_email: str
    smtp_user: str
    smtp_password: str

# ====== Email Generation Function ======
def generate_email(subject, recipient_name, context):
    prompt = f"""
    Write a professional email to {recipient_name} about: {subject}.
    Context: {context}
    """

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a professional email assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=400
    )

    return response.choices[0].message.content

# ====== Email Sending Function ======
def send_email(smtp_user, smtp_password, to_email, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], msg.as_string())

# ====== API Endpoint ======
@app.post("/send-email/")
def send_email_api(request: EmailRequest):
    # 1. Generate Email
    email_body = generate_email(request.subject, request.recipient_name, request.context)

    # 2. Send Email
    send_email(
        smtp_user=request.smtp_user,
        smtp_password=request.smtp_password,
        to_email=request.to_email,
        subject=request.subject,
        body=email_body
    )

    return {"status": "success", "message": f"Email sent to {request.to_email}", "generated_email": email_body}
