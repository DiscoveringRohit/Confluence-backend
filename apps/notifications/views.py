from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        unread_only = self.request.query_params.get('unread')
        if unread_only and unread_only.lower() in ('1', 'true'):
            qs = qs.filter(is_read=False)
        return qs

class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)

        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notif).data)

class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated_count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'message': f'Marked {updated_count} notifications as read.'})
