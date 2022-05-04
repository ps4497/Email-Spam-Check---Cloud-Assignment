import os
import json
import logging
import boto3
import email
import urllib.parse
from botocore.exceptions import ClientError
from sms_spam_classifier_utilities import one_hot_encode
from sms_spam_classifier_utilities import vectorize_sequences

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
runtime= boto3.client('runtime.sagemaker')
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']

def lambda_handler(event, context):
    
    logger.info(event)
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    data = s3.get_object(Bucket=bucket,Key= key)
    contents = data['Body'].read()
    msg = email.message_from_bytes(contents)
      
    payload = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))

        # skip any text/plain (txt) attachments
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                payload = part.get_payload(decode=True)  # decode
                print("multi part", payload)
                break
    else:
        payload = msg.get_payload()
        
    
    print("payload is ", payload.decode("utf-8"))
    payload = payload.decode("utf-8")
    payload = payload.replace('\r\n',' ').strip()
    payloadtext = payload
    
    vocabulary_length = 9013
    test_messages = [payload]
    one_hot_test_messages = one_hot_encode(test_messages, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    payload = json.dumps(encoded_test_messages.tolist())
    response = runtime.invoke_endpoint(EndpointName=ENDPOINT_NAME,ContentType='application/json',Body=payload)
    
    response_body = response['Body'].read().decode('utf-8')
    result = json.loads(response_body)
    print(result)
    pred = int(result['predicted_label'][0][0])
    if pred == 1:
        CLASSIFICATION = "SPAM"
    elif pred == 0:
        CLASSIFICATION = "NOT SPAM"
    CLASSIFICATION_CONFIDENCE_SCORE = str(float(result['predicted_probability'][0][0]) * 100)
    
    
    #########################################################################################################
    SENDER = "automation@testemail.ga"
    RECIPIENT = msg['From']
    EMAIL_RECEIVE_DATE = msg["Date"]
    EMAIL_SUBJECT = msg["Subject"]
    payloadtext = payloadtext[:240]
    EMAIL_BODY = payloadtext
    AWS_REGION = "us-east-1"

    # The email to send.
    SUBJECT = "Email Spam Detection Notification"
    BODY_TEXT = "We received your email sent at " + EMAIL_RECEIVE_DATE + " with the subject " + EMAIL_SUBJECT + ".\r\nHere is a 240 character sample of the email body:\r\n" + EMAIL_BODY + "\r\nThe email was categorized as " + CLASSIFICATION + " with a " + CLASSIFICATION_CONFIDENCE_SCORE + "% confidence."
    CHARSET = "UTF-8"
    client = boto3.client('ses',region_name=AWS_REGION)
    
    # Try to send the email.
    try:
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {

                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
            
        )

    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])    
            
            
            
            
            
            
            
            
            
           
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
