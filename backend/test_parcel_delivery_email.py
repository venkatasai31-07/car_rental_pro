import unittest
from email.message import EmailMessage

def send_parcel_delivered_email_logic(receiver, parcel_data, email_user):
    msg = EmailMessage()
    msg["Subject"] = "🎁 Your Parcel has been Delivered!"
    msg["From"] = email_user
    msg["To"] = receiver

    html = f"""
    <html>
    <body>
        <h2>✨ Parcel Delivered!</h2>
        <p>Description: {parcel_data.get("parcel_description")}</p>
        <p>Receiver Name: {parcel_data.get("receiver_name")}</p>
    </body>
    </html>
    """
    msg.add_alternative(html, subtype='html')
    return msg

class TestParcelEmail(unittest.TestCase):
    def test_email_content(self):
        try:
            receiver = "test@example.com"
            parcel_data = {
                "parcel_description": "Laptop",
                "receiver_name": "John Doe"
            }
            email_user = "sender@example.com"
            
            msg = send_parcel_delivered_email_logic(receiver, parcel_data, email_user)
            
            self.assertEqual(msg["To"], receiver)
            self.assertEqual(msg["Subject"], "🎁 Your Parcel has been Delivered!")
            
            # Use get_payload(0) if it's not multipart, or get_payload() for content
            content = msg.get_payload(0).get_content()
            self.assertIn("Laptop", content)
            self.assertIn("John Doe", content)
            print("✅ Email content verification passed!")
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            raise e

if __name__ == "__main__":
    unittest.main()
