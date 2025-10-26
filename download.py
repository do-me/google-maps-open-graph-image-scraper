import json
import os
import re
import requests
from bs4 import BeautifulSoup

def download_social_preview_images(json_input_path):
    """
    Loads data from a JSON file, handles Google's consent page automatically,
    downloads the Google Maps preview image, and saves the updated data.

    Args:
        json_input_path (str): The path to the input JSON file.
    """
    output_dir = "place_images"
    os.makedirs(output_dir, exist_ok=True)
    json_output_path = "places_with_images.json"

    try:
        with open(json_input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{json_input_path}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{json_input_path}'.")
        return

    print(f"Successfully loaded {len(data)} items from '{json_input_path}'.\n")

    # --- Use a Session object to persist cookies across requests ---
    with requests.Session() as session:
        # Set a realistic User-Agent to mimic a browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,it;q=0.8' # Prioritize English/Italian
        })

        for item in data:
            google_maps_url = item.get("Google_Maps")
            place_name = item.get("Place_Name", "unknown_place")

            if not google_maps_url:
                print(f"Skipping '{place_name}': No 'Google_Maps' URL provided.")
                item["image"] = None
                continue

            try:
                # --- Step 1: Initial GET request to the short URL ---
                # This will redirect to the consent page or the final page
                print(f"Processing '{place_name}'...")
                initial_response = session.get(google_maps_url, timeout=15)
                initial_response.raise_for_status()

                soup = BeautifulSoup(initial_response.text, 'html.parser')

                # --- Step 2: Check if it's a consent page and handle it ---
                # Find all forms on the page
                consent_forms = soup.find_all('form', action=re.compile('https://consent.google.com/save'))
                
                if consent_forms:
                    print("   Consent page detected. Attempting to accept...")
                    # We will try to submit the "Accept All" form. Usually, it's the second one.
                    # This is a bit of a guess, but it's a common pattern.
                    form_to_submit = consent_forms[-1] # Often "Accept all" is the last form
                    
                    form_action = form_to_submit['action']
                    form_data = {}
                    
                    # Extract all hidden input fields from the form
                    for input_tag in form_to_submit.find_all('input'):
                        name = input_tag.get('name')
                        value = input_tag.get('value', '')
                        if name:
                            form_data[name] = value

                    # The 'Accept all' button often has a specific name or value
                    # In this case, we're assuming the form structure is correct.
                    # We might need to add specific button values if required.
                    
                    # Make a POST request to submit the consent form
                    consent_post_response = session.post(form_action, data=form_data, timeout=15)
                    consent_post_response.raise_for_status()
                    
                    # After consenting, the session should have the right cookies.
                    # Now, re-fetch the original URL using the same session.
                    print("   Consent submitted. Re-fetching the page...")
                    final_response = session.get(google_maps_url, timeout=15)
                    final_response.raise_for_status()
                    soup = BeautifulSoup(final_response.text, 'html.parser')
                else:
                    # If no consent form was found, the initial response is the one we need
                    final_response = initial_response

                # --- Step 3: Now parse the actual content page for the image ---
                image_tag = soup.find("meta", attrs={"itemprop": "image"}) or soup.find("meta", attrs={"property": "og:image"})

                if image_tag and image_tag.get("content"):
                    image_url = image_tag["content"]

                    sanitized_name = re.sub(r'[\\/*?:"<>|]', "", place_name).replace(" ", "_")
                    image_filename = f"{sanitized_name}.jpg"
                    image_path = os.path.join(output_dir, image_filename)

                    # Download the image using the same session
                    image_response = session.get(image_url, timeout=15)
                    image_response.raise_for_status()
                    with open(image_path, "wb") as f:
                        f.write(image_response.content)

                    item["image"] = image_path
                    print(f"✅ Success: Image downloaded for '{place_name}'")
                else:
                    item["image"] = None
                    print(f"⚠️ Warning: Could not find an image meta tag for '{place_name}' after handling redirects.")

            except requests.exceptions.Timeout:
                print(f"❌ Error: The request timed out for '{place_name}'.")
                item["image"] = None
            except requests.exceptions.RequestException as e:
                print(f"❌ Error: Failed to fetch data for '{place_name}'. Reason: {e}")
                item["image"] = None

    # --- Step 4: Save the modified data to a new JSON file ---
    with open(json_output_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("\n-------------------------------------------------")
    print("Processing complete.")
    print(f"Images have been saved in the '{output_dir}' directory.")
    print(f"The updated JSON data has been saved to '{json_output_path}'.")


if __name__ == "__main__":
    input_file = "locations.json"
    download_social_preview_images(input_file)
