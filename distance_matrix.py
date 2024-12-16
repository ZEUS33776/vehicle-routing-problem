import urllib.request
import json
from config import API_KEY

def create_distance_matrix(coordinates):
    API_key = API_KEY
    max_elements = 100
    num_locations = len(coordinates)
    max_rows = max_elements // num_locations
    q, r = divmod(num_locations, max_rows)
    dest_coordinates = coordinates
    distance_matrix = []

    for i in range(q):
        origin_coordinates = coordinates[i * max_rows: (i + 1) * max_rows]
        response = send_request(origin_coordinates, dest_coordinates, API_key)
        distance_matrix += build_distance_matrix(response)

    if r > 0:
        origin_coordinates = coordinates[q * max_rows: q * max_rows + r]
        response = send_request(origin_coordinates, dest_coordinates, API_key)
        distance_matrix += build_distance_matrix(response)

    return distance_matrix

def send_request(origin_coordinates, dest_coordinates, API_key):
    def build_coordinate_str(coordinates):
        return '|'.join(f"{lat},{lng}" for lat, lng in coordinates)

    request_url = 'https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial'
    origin_coordinate_str = build_coordinate_str(origin_coordinates)
    dest_coordinate_str = build_coordinate_str(dest_coordinates)
    request_url += f'&origins={origin_coordinate_str}&destinations={dest_coordinate_str}&key={API_key}'

    with urllib.request.urlopen(request_url) as response:
        json_result = response.read()
    return json.loads(json_result)

def build_distance_matrix(response):
    return [
        [row['elements'][j]['distance']['value'] for j in range(len(row['elements']))]
        for row in response['rows']
    ]
