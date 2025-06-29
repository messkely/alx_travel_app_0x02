from rest_framework import viewsets, status
from .models import Listing, Booking, Payment
from .serializers import ListingSerializer, BookingSerializer
import requests
import os
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response

class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

CHAPA_SECRET_KEY = os.getenv('CHAPA_SECRET_KEY')
CHAPA_BASE_URL = "https://api.chapa.co/v1"

class InitiatePaymentView(APIView):
    def post(self, request):
        data = request.data
        booking_reference = str(uuid.uuid4())
        email = data.get('email')
        amount = data.get('amount')

        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
        }

        payload = {
            "amount": amount,
            "currency": "ETB",
            "email": email,
            "tx_ref": booking_reference,
            "callback_url": "http://localhost:8000/api/verify-payment/",
            "return_url": "http://localhost:8000/payment-success/",
            "customization[title]": "Travel Booking",
            "customization[description]": "Secure travel booking via Chapa"
        }

        response = requests.post(f"{CHAPA_BASE_URL}/transaction/initialize", headers=headers, data=payload)

        if response.status_code == 200:
            res_data = response.json()
            Payment.objects.create(
                booking_reference=booking_reference,
                amount=amount,
                status='Pending',
                transaction_id=res_data['data']['tx_ref'],
                email=email,
            )
            return Response({"payment_url": res_data['data']['checkout_url']}, status=200)
        return Response(response.json(), status=response.status_code)
class VerifyPaymentView(APIView):
    def get(self, request):
        tx_ref = request.query_params.get('tx_ref')
        if not tx_ref:
            return Response({"error": "tx_ref is required"}, status=400)

        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
        }

        response = requests.get(f"{CHAPA_BASE_URL}/transaction/verify/{tx_ref}", headers=headers)

        if response.status_code == 200:
            result = response.json()
            status_str = result['data']['status']
            try:
                payment = Payment.objects.get(transaction_id=tx_ref)
                if status_str == 'success':
                    payment.status = 'Completed'
                else:
                    payment.status = 'Failed'
                payment.save()
                return Response({"status": payment.status}, status=200)
            except Payment.DoesNotExist:
                return Response({"error": "Payment not found"}, status=404)
        return Response(response.json(), status=response.status_code)
