from flask import Flask, request
import logging
import json
import random
from flask_ngrok import run_with_ngrok
from pymorphy2 import MorphAnalyzer

app = Flask(__name__)
run_with_ngrok(app)
morph = MorphAnalyzer()

logging.basicConfig(level=logging.INFO)

cities = {
    'москва': ['213044/f941427aac9aabc95435', '1030494/41d738db8fc467c9c36d'],
    'нью-йорк': ['965417/5c0f54bb69164b77b774', '1521359/232156d9413b419de6ad'],
    'париж': ["937455/74b8f8f071332f4eddf5", '997614/0b95cbcc02bdd739ecb3']
}

yes_no_btns = [
    {
        'title': 'Да',
        'hide': True
    },
    {
        'title': 'Нет',
        'hide': True
    }
]
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
    if "buttons" not in response["response"]:
        response["response"]["buttons"] = []
    sessionStorage[request.json['session']['user_id']]["last_buttons"] = response["response"][
        "buttons"].copy()
    response["response"]["buttons"].append({
        "title": "Помощь",
        "hide": True
    })
    logging.info('Response: %r', response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        sessionStorage[user_id] = {
            'first_name': None,
            'game_started': False,
            "played": False,
            "points": 0
        }
    elif "помощь" in req["request"]["nlu"]["tokens"]:
        points = sessionStorage[user_id]['points']
        res["response"]["text"] = (
                (
                    f"Я знаю, что тебя зовут {sessionStorage[user_id]['first_name'].capitalize()}. "
                    if sessionStorage[user_id]["first_name"] else
                    "Я не знаю как тебя зовут. "
                ) +
                (
                    (
                        f"Ты отгадал {points} {morph.parse('город')[0].make_agree_with_number(points).word} из {len(sessionStorage[user_id]['guessed_cities'])}."
                        if points else
                        "Ты отгадал ничего"
                    )
                    if sessionStorage[user_id]["played"] else
                    "Ты еще не начинал играть."
                ) +
                (
                    f" Загаданный город начинается на букву \"{sessionStorage[user_id]['city'][0].upper()}\""
                    if sessionStorage[user_id]["game_started"] else
                    ""
                )
        )
        res["response"]["buttons"] = sessionStorage[user_id]["last_buttons"]
    elif sessionStorage[user_id]['first_name'] is None:
        first_name = get_first_name(req)
        if first_name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'
        else:
            sessionStorage[user_id]['first_name'] = first_name
            sessionStorage[user_id]['guessed_cities'] = []
            res['response'][
                'text'] = f'Приятно познакомиться, {first_name.title()}. Я Алиса. Отгадаешь город по фото?'
            res['response']['buttons'] = yes_no_btns.copy()
    else:
        if not sessionStorage[user_id]['game_started']:
            if 'да' in req['request']['nlu']['tokens']:
                if len(sessionStorage[user_id]['guessed_cities']) == 3:
                    res['response']['text'] = 'Ты отгадал все города!'
                    res["response"]['end_session'] = True
                else:
                    sessionStorage[user_id]['game_started'] = True
                    sessionStorage[user_id]['attempt'] = 1
                    play_game(res, req)
            elif 'нет' in req['request']['nlu']['tokens']:
                res['response']['text'] = 'Ну и ладно!'
                res["response"]['end_session'] = True
            elif "покажи город на карте" == req["request"]["original_utterance"].lower() and {
                        "title": "Покажи город на карте",
                        "url": f"https://yandex.ru/maps/?mode=search&text={sessionStorage[user_id]['city']}",
                        "hide": True
                    } in sessionStorage[user_id]["last_buttons"]:
                mest = {
                    "femn": "она",
                    "neut": "оно",
                    "masc": "он"
                }[morph.parse(sessionStorage[user_id]['city'])[0].tag.gender]
                res["response"][
                    "text"] = f"Вот {mest} {sessionStorage[user_id]['city'].capitalize()}! Сыграем еще?"
                res["response"]["buttons"] = sessionStorage[user_id]["last_buttons"]
            else:
                res['response']['text'] = 'Не поняла ответа! Так да или нет?'
                res['response']['buttons'] = yes_no_btns.copy()
        else:
            play_game(res, req)


def play_game(res, req):
    user_id = req['session']['user_id']
    sessionStorage[user_id]["played"] = True
    attempt = sessionStorage[user_id]['attempt']
    if attempt == 1:
        city = random.choice(list(cities))
        while city in sessionStorage[user_id]['guessed_cities']:
            city = random.choice(list(cities))
        sessionStorage[user_id]['city'] = city
        res['response']['card'] = {}
        res['response']['card']['type'] = 'BigImage'
        res['response']['card']['title'] = 'Что это за город?'
        res['response']['card']['image_id'] = cities[city][attempt - 1]
        res['response']['text'] = 'Тогда сыграем!'
    else:
        city = sessionStorage[user_id]['city']
        if get_city(req) == city:
            res['response']['text'] = 'Правильно! Сыграем ещё?'
            sessionStorage[user_id]['guessed_cities'].append(city)
            res["response"]["buttons"] = [
                *yes_no_btns,
                {
                    "title": "Покажи город на карте",
                    "url": f"https://yandex.ru/maps/?mode=search&text={sessionStorage[user_id]['city']}",
                    "hide": True
                }
            ]
            sessionStorage[user_id]["points"] += 1
            sessionStorage[user_id]['game_started'] = False
            return
        else:
            if attempt == 3:
                res['response']['text'] = f'Вы пытались. Это {city.title()}. Сыграем ещё?'
                res["response"]["buttons"] = [
                    *yes_no_btns,
                    {
                        "title": "Покажи город на карте",
                        "url": f"https://yandex.ru/maps/?mode=search&text={sessionStorage[user_id]['city']}",
                        "hide": True
                    }
                ]
                sessionStorage[user_id]['game_started'] = False
                sessionStorage[user_id]['guessed_cities'].append(city)
                return
            else:
                res['response']['card'] = {}
                res['response']['card']['type'] = 'BigImage'
                res['response']['card']['title'] = 'Неправильно. Вот тебе дополнительное фото'
                res['response']['card']['image_id'] = cities[city][attempt - 1]
                res['response']['text'] = 'А вот и не угадал!'
    sessionStorage[user_id]['attempt'] += 1


def get_city(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.GEO':
            return entity['value'].get('city', None)


def get_first_name(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.FIO':
            return entity['value'].get('first_name', None)


if __name__ == '__main__':
    app.run()
