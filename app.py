import os
from flask import Flask, request, abort, jsonify
from flask_restx import Resource, Api
import re
from functools import wraps
import urllib.request
import dns.resolver
import json
from fuzzywuzzy import fuzz 
from fuzzywuzzy import process
import boto3
import shortuuid
from datetime import datetime
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity
from azure.cosmosdb.table import TableService

key = "45374496f48b4743a09b767eb5e6c07a"
endpoint = "https://zura-digital.cognitiveservices.azure.com/"

url_https_regex = re.compile(r"https?://www\.?\w+\.\w+")
url_regex = re.compile(r"ht*?://www\.?\w+\.\w+")
number = re.compile(r'\d')

#disposable list

url = "https://s3.ap-south-1.amazonaws.com/zuradigital.com/work-example/disposable-Email.txt"
spam_email_list = urllib.request.urlopen(url)
spam_email_list = list(spam_email_list)

#spammers list

url = "https://s3.ap-south-1.amazonaws.com/zuradigital.com/work-example/free-domain-list.txt"
free_email_list = urllib.request.urlopen(url)
free_email_list = list(free_email_list)

# blacklist emails

url = "https://s3.ap-south-1.amazonaws.com/zuradigital.com/work-example/spammers.txt"
blacklist = urllib.request.urlopen(url)
blacklist= list(blacklist)

app = Flask(__name__)

authorizations = {
    'apikey' : {
        'type' : 'apiKey',
        'in' : 'header',
        'name' : 'X-API-KEY'
    }
}

api = Api(app, authorizations=authorizations)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        token = None

        if 'X-API-KEY' in request.headers:
            token = request.headers['X-API-KEY']

        if not token:
            return {'message' : 'Token is missing.'}, 401

        if token != "mytoken":
            return {'message' : 'Your Token is wrong please contact ajay.mamgain2007@gmail.com'}, 401

        print('TOKEN: {}'.format(token))
        return f(*args, **kwargs)

    return decorated


def authenticate_client():
    ta_credential = AzureKeyCredential(key)
    text_analytics_client = TextAnalyticsClient(
        endpoint=endpoint,
        credential=ta_credential,
        api_version="TextAnalyticsApiVersion.V3_0")
    return text_analytics_client


client = authenticate_client()

@api.route('/Spam',methods=['POST'])
class spam(Resource):
    @api.doc(security='apikey')
    @token_required
    def post(self):
        if  request.method == 'POST':
            data = request.get_json(force=True)
            email = data['Email'].lower()
            comments = data['Comment']
            firstName = data['firstName'].capitalize()
            lastName = data['lastName'].capitalize()
            fullName = (firstName +" "+ lastName).lower()
            localpart = email.split("@")[0]
            domain = email.split("@")[1]

    # code to check number in full name
            Name = number.search(fullName)
            if Name==None:
                nameError = "Name has no error"
            else:
                nameError = "Name contains a digit Spam"

    # code to check local part name with full name
            localscore = fuzz.ratio(localpart,fullName)
            if localscore >= 50:
                has_suspectable_localpart  = False
            else:
                has_suspectable_localpart = True

    # code to check Email syntax
            validEmail = re.match(
                '^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)

            if validEmail == None:
                    validEmail = "Bad Syntax"
            else:
                    validEmail = "Valid Syntax"

            if validEmail == "Valid Syntax":
                spam_highlist = process.extractOne(domain, spam_email_list)
                if spam_highlist[1] >= 90:
                    spam_note = "Spam Email with spam score " + \
                        str(spam_highlist[1]) + " similar with domain " + str(spam_highlist[0])
                else:
                    spam_note = "No domain found with 90 Spam score"
            else:
                spam_note = "No Need"
    # code to check free email domain

            if (validEmail == "Valid Syntax"):
                try:                
                    results = dns.resolver.query(
                        domain, "MX", raise_on_no_answer=False, lifetime=5)
                    if results is not None:
                        mxRecord = ("Found ") + str(results.rrset[0])
                    else:
                        mxRecord = ("Not Found with None value")
                except (dns.resolver.NXDOMAIN):
                        mxRecord = "No Named Domain"
                except (dns.exception.Timeout):
                        mxRecord = "timedout"
                except:
                        mxRecord = "No record Found"
            else:
                mxRecord = "No Need"
# code to check the sentiments of the comments
            def sentiment_analysis(client):
                documents = [comments]
                date = datetime.now()
                id = shortuuid.uuid()
                filename = str(id) + ".json"
                response = client.analyze_sentiment(documents=documents)[0]
                print("Document Sentiment: {}".format(response.sentiment))
                sentiment = response.sentiment
                
                the_connection_string = "DefaultEndpointsProtocol=https;AccountName=hackerearthdb;AccountKey=qcE643oYVF3wNjZBWa892wjgqZJpVGnaH9jySboAMDoAwjoh9OCo9zqIXGbOBXyLVW8fYtkhF2dNhL4io0iTag==;TableEndpoint=https://hackerearthdb.table.cosmos.azure.com:443/;"
                table_service= TableService(endpoint_suffix="table.cosmos.azure.com",
                            connection_string=the_connection_string)
                data = {
                    'email': email, 'spam_note': spam_note, 'validEmail': validEmail,
                    'mxRecord': mxRecord, 'comment': comments, 'datetime': str(date),
                    'sentiment': sentiment, 'PartitionKey': 'Zuradigital', 'RowKey': id
                }

                table_service.insert_or_replace_entity('zuradigital', data)

                body = json.dumps(data, sort_keys=True, indent=5)
                print(body)

            sentiment_analysis(client)
            
            return {'result': 'data has been uploaded in cosmosdb'}

        else:
            abort(400)

if __name__ == '__main__':
    app.run()
