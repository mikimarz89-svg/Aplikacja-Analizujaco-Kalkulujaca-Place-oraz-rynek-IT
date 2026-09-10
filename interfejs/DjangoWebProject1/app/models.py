from django.db import models

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Offer(models.Model):
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True, null=True)
    
    # Pensje
    salary_min = models.IntegerField(blank=True, null=True)
    salary_max = models.IntegerField(blank=True, null=True)
    currency = models.CharField(max_length=10, null=True, blank=True)
    
    # Metadane
    work_mode = models.CharField(max_length=50, blank=True, null=True)
    contract_type = models.CharField(max_length=50, blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)
    
    # Relacja do Tagów
    tags = models.ManyToManyField(Tag, related_name='offers', blank=True)

    def __str__(self):
        return f"{self.title} ({self.salary_min}-{self.salary_max} {self.currency})"
        
    @property
    def mean_salary(self):
        if self.salary_min and self.salary_max:
            return (self.salary_min + self.salary_max) / 2
        return self.salary_min or self.salary_max or 0