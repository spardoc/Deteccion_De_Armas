from smtplib import SMTPException
from alertupload_rest.serializers import UploadAlertSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import BadHeaderError, JsonResponse
from threading import Thread
from django.core.mail import send_mail
import re

# Thread decorator definition
def start_new_thread(function):
    def decorator(*args, **kwargs):
        t = Thread(target = function, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
    return decorator

@api_view(['POST'])
def post_alert(request):
    serializer = UploadAlertSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        identify_email_sms(serializer)
    else:
        return JsonResponse({'error': 'Unable to process data!'}, status=400)
    return Response(request.META.get('HTTP_AUTHORIZATION'))

# Identifies if the user provided an email or a mobile number
def identify_email_sms(serializer):
    if(re.search('^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$', serializer.data['alert_receiver'])):  
        print("Valid Email")
        send_email(serializer)
    elif re.compile("[+593][0-9]{10}").match(serializer.data['alert_receiver']):
        # 1) Begins with +593
        # 2) Then contains 10 digits 
        print("Valid Mobile Number")
    else:
        print("Invalid Email or Mobile number")

# Sends email
@start_new_thread
def send_email(serializer):
    try:
        send_mail(
            'Weapon Detected!', 
            prepare_alert_message(serializer), 
            'samuelpardo1997@gmail.com',
            [serializer.data['alert_receiver']],
            fail_silently=False,  # Set to False to capture exceptions
        )
        print("Correo enviado exitosamente")
    except Exception as e:
        print("Error al enviar el correo:", e)

# Prepares the alert message
def prepare_alert_message(serializer):
    uuid_with_slashes = split(serializer.data['image'], ".")
    uuid = split(uuid_with_slashes[3], "/")
    url = 'http://127.0.0.1:8000/alert' + uuid[2]
    return 'Weapon Detected! View alert at ' + url

# Splits string into a list
def split(value, key):
    return str(value).split(key)