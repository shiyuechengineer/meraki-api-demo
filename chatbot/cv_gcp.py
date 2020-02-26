import io

import cv2

from chatbot import *

# Imports the Google Cloud client library
from google.cloud import vision
from google.cloud.vision import types


# Performs label detection on the image file
def label_detection(client, image):
    response = client.label_detection(image=image)
    return response.label_annotations


# Performs landmark detection on the image file
def landmark_detection(client, image):
    response = client.landmark_detection(image=image)
    return response.landmark_annotations


# Performs logo detection on the image file
def logo_detection(client, image):
    response = client.logo_detection(image=image)
    return response.logo_annotations


# Performs text detection on the image file
def text_detection(client, image):
    response = client.text_detection(image=image)
    return response.text_annotations


# Performs face detection on the image file
def face_detection(client, image):
    response = client.face_detection(image=image)
    return response.face_annotations


# Performs object detection on the image file
def object_detection(client, image):
    response = client.object_localization(image=image)
    return response.localized_object_annotations


# Overall analysis function
def analyze_image(file_name):
    # Instantiates a client
    client = vision.ImageAnnotatorClient()

    # Loads the image into memory
    with io.open(file_name, 'rb') as image_file:
        content = image_file.read()

    image = types.Image(content=content)

    # Analyze image
    labels = label_detection(client, image)
    landmarks = landmark_detection(client, image)
    logos = logo_detection(client, image)
    texts = text_detection(client, image)
    faces = face_detection(client, image)
    objects = object_detection(client, image)

    # Return analysis
    return {
        'labels': labels,
        'landmarks': landmarks,
        'logos': logos,
        'texts': texts,
        'faces': faces,
        'objects': objects
    }


# Send snapshot to GCP for analysis
def gcp_vision(session, headers, payload, file, message='', folder=None):
    # Structure file path correctly
    file_path = f'{folder}/{file}' if folder else f'{file}'
    print(file_path)

    # Analyze and annotate file type
    analysis = analyze_image(file_path)
    if '.jpg' or '.jpeg' in file:
        file_type = 'image/jpg'
    elif '.png' in file:
        file_type = 'image/png'

    # For faces, names of likelihood from google.cloud.vision.enums
    likelihood_name = ('UNKNOWN', 'VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE', 'LIKELY', 'VERY_LIKELY')
    counter = 1
    if analysis['faces']:
        img = cv2.imread(f'{file_path}')
        font = cv2.FONT_HERSHEY_SIMPLEX
        message += f'\n\n**Faces** detected:'
        for face in analysis['faces']:
            trait_shown = False
            message += f'\n- {counter} - '
            traits = {
                'joy': face.joy_likelihood,
                'sorrow': face.sorrow_likelihood,
                'anger': face.anger_likelihood,
                'surprise': face.surprise_likelihood,
                'underexposed': face.under_exposed_likelihood,
                'blurred': face.blurred_likelihood,
                'headwear': face.headwear_likelihood,
            }
            for trait in traits:
                if likelihood_name[traits[trait]] not in ('UNKNOWN', 'VERY_UNLIKELY'):
                    trait_shown = True
                    likelihood = likelihood_name[traits[trait]].lower().replace('_', ' ')
                    message += f'**{trait}** (_{likelihood}_), '
            if not trait_shown:
                message = message[:-3]
            else:
                message = message[:-2]

            # Draw box around face
            vertices = face.bounding_poly.vertices
            top_left = (vertices[0].x, vertices[0].y)
            bottom_right = (vertices[2].x, vertices[2].y)

            img = cv2.rectangle(img, top_left, bottom_right, (0, 255, 0), 3)
            img = cv2.putText(img, str(counter), (top_left[0] + 10, top_left[1] + 50), font, 2, (0, 0, 255),
                              1, cv2.LINE_AA)
            counter += 1
        new_file = f'/tmp/{file[:file.rindex(".")]}.png'
        cv2.imwrite(new_file, img)

    # Analyze image for labels
    labels = analysis['labels'][:10]
    message += f'\n\nTop {len(labels)} **labels** detected (w/ _confidence scores_):'
    for label in labels:
        message += f'\n- **{label.description}** (_{round(label.score * 100, 1)}_)'

    # Return other interesting things
    if analysis['landmarks']:
        message += f'\n\n**Landmarks** detected (w/ _scores_):'
        for landmark in analysis['landmarks']:
            message += f'\n- **{landmark.description}** (_{round(landmark.score * 100, 1)}_)'
    if analysis['logos']:
        message += f'\n\n**Logos** detected (w/ _scores_):'
        for logo in analysis['logos']:
            message += f'\n- **{logo.description}** (_{round(logo.score * 100, 1)}_)'
    if analysis['texts']:
        message += f'\n\n**Texts** detected:'
        for text in analysis['texts'][1:]:
            message += f'\n- {text.description}'

    # Analyze image for objects
    objects = analysis['objects'][:10]
    if objects:
        message += f'\n\nTop {len(objects)} **objects** detected (w/ _confidence scores_):'
        for object in objects:
            message += f'\n- **{object.name}** (_{round(object.score * 100, 1)}_)'

    # Send annotated image if faces, otherwise original
    if analysis['faces']:
        send_file(session, headers, payload, message, new_file, file_type='image/png')
    else:
        send_file(session, headers, payload, message, file_path, file_type=file_type)
