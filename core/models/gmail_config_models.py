from django.db import models

class gmailShareConfig(models.Model):
    gmail_user = models.EmailField(default="littlecapa@googlemail.com")
    source_folder = models.CharField(max_length=255, default="Aktien")
    target_folder = models.CharField(max_length=255, default="Archive_Aktien")
    save_path = models.CharField(max_length=500, default="/Volumes/Data/DataLake/Finance/Test")

    def __str__(self):
        return f"AppConfig for {self.gmail_user}"