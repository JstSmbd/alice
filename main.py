from flask import Flask, request, jsonify
import logging
import json
from flask_ngrok import run_with_ngrok
from geo import get_distance, get_geo_info

app = Flask(__name__)
run_with_ngrok(app)

logging.basicConfig(level=logging.INFO, filename='app.log',
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)
    logging.info('Request: %r', response)
    return jsonify(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    if req['session']['new']:
        sessionStorage[user_id] = {
            "name": None
        }
        res['response']['text'] = \
            'Привет! Как тебя зовут?'
        return
    name = sessionStorage[user_id]["name"]
    if name is None:
        next_name = get_name(req)
        if next_name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'
        else:
            sessionStorage[user_id]['name'] = next_name
            res['response']['text'] = f'Приятно познакомиться, {next_name.title()}. Я Алиса. ' \
                                      f'Я могу показать город или сказать расстояние между городами!'
    else:
        cities = get_cities(req)
        if not cities:
            res['response']['text'] = f'{name.title()}, ты не написал название не одного города!'
        elif len(cities) == 1:
            res['response']['text'] = f'Этот город в стране - {get_geo_info(cities[0], "country")}, ' \
                                      f'теперь будешь знать, {name.title()}!'
        elif len(cities) == 2:
            distance = get_distance(get_geo_info(
                cities[0], "coordinates"), get_geo_info(cities[1], "coordinates"))
            res['response']['text'] = f'Расстояние между этими городами: {str(round(distance))} ' \
                                      f'км, вот так, {name.title()}.'
        else:
            res['response']['text'] = f'Слишком много городов, {name.title()}!'


def get_cities(req):
    cities = []
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.GEO':
            if 'city' in entity['value']:
                cities.append(entity['value']['city'])
    return cities


def get_name(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.FIO':
            return entity['value'].get('first_name', None)


if __name__ == '__main__':
    app.run()