from django.urls import path
from . import views

app_name = 'stations'

urlpatterns = [
    path('', views.home_page, name='home'),
    path('upload-csv/', views.upload_csv, name='upload_csv'),
    path('api/stations', views.stations_api, name='stations_api'),
    path('api/connectors', views.connectors_api, name='connectors_api'),
    path('api/operators', views.operators_api, name='operators_api'),
    path('api/power-levels', views.power_levels_api, name='power_levels_api'),
    path('api/address', views.address_api, name='address_api'),
    path('api/search', views.search_api, name='search_api'),
    path('api/zones/summary', views.zones_summary_api, name='zones_summary_api'),
]
