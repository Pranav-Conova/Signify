from django.urls import path
from .views import upload_file,index,save_gestures

urlpatterns = [
    path("", upload_file, name="upload_file"),
    path("index/", index, name="index"),
    path("api/save-gestures/", save_gestures, name="save_gestures"),
    
]