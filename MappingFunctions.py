import requests
import folium
import googlemaps

'''
This function calls the API, and returns three items:
1. leg_lengths_miles = A list containing the distances of each leg of travel
2. polyline = A polyline showing the travel route
'''

def get_distances_and_polyline(origin, destination, api_key):
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": api_key,
        "units": "imperial"
    }

    response = requests.get(base_url, params=params)
    data = response.json()

    if data["status"] == "OK":
        # Extracting the length of each leg in miles
        leg_lengths_miles = [step["distance"]["text"] for step in data["routes"][0]["legs"][0]["steps"]]

        # Extracting the polyline
        polyline = data["routes"][0]["overview_polyline"]["points"]

        return leg_lengths_miles, polyline
    else:
        return None, None


# These functions are used to locate the half-way point, the full travel distance, and the leg on which the half-way point occurs

def convert_to_miles(distance_str):
    if 'mi' in distance_str:
        return float(distance_str.replace(' mi', ''))
    elif 'ft' in distance_str:
        return float(distance_str.replace(' ft', '')) / 5280.0
    else:
        return 0.0

def calculate_total_distance(distances):
    total_miles = sum(convert_to_miles(d) for d in distances)
    return total_miles

def calculate_halfway_point(distances):
    total_miles = calculate_total_distance(distances)
    halfway_miles = total_miles / 2.0

    accumulated_distance = 0.0
    halfway_leg = None
    for i, d in enumerate(distances):
        distance_in_miles = convert_to_miles(d)
        accumulated_distance += distance_in_miles
        if accumulated_distance >= halfway_miles:
            halfway_leg = i
            break

    return halfway_miles, halfway_leg

def process_distance_list(distance_list):
    total_distance = calculate_total_distance(distance_list)
    halfway_miles, halfway_leg = calculate_halfway_point(distance_list)
    return total_distance, halfway_miles, halfway_leg   

# Converts the Polyline result to information which can be mapped
def decode_polyline(polyline_str):
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    # Coordinates have variable length when encoded, so just keep
    # track of whether we've hit the end of the string. In each
    # while loop iteration, a single coordinate is decoded.
    while index < len(polyline_str):
        # Gather lat/lon changes, store them in a dictionary to apply them later
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0

            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break

            if result & 1:
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)

        lat += changes['latitude']
        lng += changes['longitude']

        coordinates.append((lat / 100000.0, lng / 100000.0))

    return coordinates

# Finds midpoint of Polyline
def find_middle_point(coordinates):
    # Calculate the middle point
    total_points = len(coordinates)
    middle_index = total_points // 2

    # Return the middle point's coordinates
    middle_lat, middle_lon = coordinates[middle_index]
    return middle_lat, middle_lon

def plot_polyline_on_map(polyline_str, api_key):
    decoded_coordinates = decode_polyline(polyline_str)

    # Calculate the center of the polyline to set the initial map view
    center_lat = sum(lat for lat, lon in decoded_coordinates) / len(decoded_coordinates)
    center_lon = sum(lon for lat, lon in decoded_coordinates) / len(decoded_coordinates)

    # Create a map centered on the polyline using Google Maps API
    mymap = folium.Map(location=[center_lat, center_lon], zoom_start=8)

    # Add the polyline to the map using Google Maps API
    polyline = folium.PolyLine(locations=decoded_coordinates, color='blue')
    mymap.add_child(polyline)

    # Find and mark the middle point of the polyline
    middle_lat, middle_lon = find_middle_point(decoded_coordinates)
    folium.Marker(location=[middle_lat, middle_lon], popup="Middle Point", icon=folium.Icon(color='green')).add_to(mymap)

    # Perform a nearby search for hotels using Google Maps Places API
    hotels_api_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    api_key = api_key

    hotel_params = {
        "location": f"{center_lat},{center_lon}",
        "rankby": "distance",
        "type": "lodging",
        "key": api_key
    }

    hotel_response = requests.get(hotels_api_url, params=hotel_params)
    if hotel_response.status_code == 200:
        hotels_data = hotel_response.json()
        closest_hotel = hotels_data.get("results", [])[0]  # The closest hotel will be the first result since we use "rankby=distance"
        if closest_hotel:
            hotel_name = closest_hotel.get("name")
            hotel_address = closest_hotel.get("vicinity")
            hotel_lat = closest_hotel.get("geometry", {}).get("location", {}).get("lat")
            hotel_lng = closest_hotel.get("geometry", {}).get("location", {}).get("lng")
            folium.Marker(location=[hotel_lat, hotel_lng], popup=f"Hotel: {hotel_name}\nAddress: {hotel_address}", icon=folium.Icon(color='purple')).add_to(mymap)

    # Perform a nearby search for restaurants using Google Maps Places API
    restaurants_params = {
        "location": f"{center_lat},{center_lon}",
        "rankby": "distance",
        "type": "restaurant",
        "key": api_key
    }

    restaurants_response = requests.get(hotels_api_url, params=restaurants_params)
    if restaurants_response.status_code == 200:
        restaurants_data = restaurants_response.json()
        closest_restaurant = restaurants_data.get("results", [])[0]  # The closest restaurant will be the first result since we use "rankby=distance"
        if closest_restaurant:
            restaurant_name = closest_restaurant.get("name")
            restaurant_address = closest_restaurant.get("vicinity")
            restaurant_lat = closest_restaurant.get("geometry", {}).get("location", {}).get("lat")
            restaurant_lng = closest_restaurant.get("geometry", {}).get("location", {}).get("lng")
            folium.Marker(location=[restaurant_lat, restaurant_lng], popup=f"Restaurant: {restaurant_name}\nAddress: {restaurant_address}", icon=folium.Icon(color='blue')).add_to(mymap)

    return mymap, hotel_name, hotel_address, restaurant_name, restaurant_address