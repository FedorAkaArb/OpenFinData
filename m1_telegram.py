import telebot
import requests
from telebot import types

import constants
import config

from m1_manager import MessengerManager

API_TOKEN = config.TELEGRAM_API_TOKEN1
bot = telebot.TeleBot(API_TOKEN)


# /start command handler; send start-message to the user
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, constants.TELEGRAM_START_MSG, parse_mode='HTML')


# /help command handler; send hello-message to the user
@bot.message_handler(commands=['help'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        constants.HELP_MSG,
        parse_mode='HTML',
        reply_markup=constants.HELP_KEYBOARD,
        disable_web_page_preview=True)


# /search message handler
@bot.message_handler(commands=['search'])
def repeat_all_messages(message):
    command_length = len('search')
    message_text = message.text[command_length + 2:].lower()
    if message_text != '':
        r = MessengerManager.make_request(message_text, 'TG')
        if len(r.messages) == 1:
            bot.send_message(message.chat.id, r.messages[0])
        else:
            for m in r.messages:
                bot.send_message(message.chat.id, m)
            if r.is_file:
                path = r.path + '\\'
                file1 = open(path + r.file_names[0], 'rb')
                file2 = open(path + r.file_names[1], 'rb')
                bot.send_document(message.chat.id, file1)
                bot.send_document(message.chat.id, file2)

    else:
        bot.send_message(message.chat.id, constants.MSG_NO_BUTTON_SUPPORT, parse_mode='HTML')


# Text handler
@bot.message_handler(content_types=['text'])
def salute(message):
    print(message.text)
    msg = MessengerManager.greetings(message.text)
    if msg:
        bot.send_message(message.chat.id, msg)


# inline mode handler
@bot.inline_handler(lambda query: len(query.query) >= 0)
def query_text(query):
    input_message_content = query.query

    m2_result = MessengerManager.make_request_m2(input_message_content, 'TG-INLINE')

    result_array = []
    if m2_result.status is False:  # in case the string is not correct we ask user to keep typing
        msg = types.InlineQueryResultArticle(id='0',
                                             title='Продолжайте ввод запроса',
                                             input_message_content=types.InputTextMessageContent(
                                                 message_text=input_message_content + '\nЗапрос не удался😢'
                                             ))
        result_array.append(msg)  # Nothing works without this list, I dunno why :P
        bot.answer_inline_query(query.id, result_array)

    else:
        m3_result = MessengerManager.make_request_m3(m2_result)
        try:
            if m3_result.data is False:
                msg_append_text = ': ' + constants.ERROR_NULL_DATA_FOR_SUCH_REQUEST_SHORT
                title = 'Данных нет'
            else:
                msg_append_text = ':\n' + str(m3_result.number)
                title = str(m3_result.number)

            msg = types.InlineQueryResultArticle(id='1',
                                                 title=title,
                                                 input_message_content=types.InputTextMessageContent(
                                                     message_text=input_message_content + msg_append_text),
                                                 )
            result_array.append(msg)

        finally:
            bot.answer_inline_query(query.id, result_array)


@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
    r = MessengerManager.parse_voice(file.content, "TG")

    if type(r) is str:
        bot.send_message(message.chat.id, r.messages[0])
    else:
        if len(r.messages) == 1:
            bot.send_message(message.chat.id, r.messages[0])
        else:
            for m in r.messages:
                bot.send_message(message.chat.id, m)
            if r.is_file:
                path = r.path + '\\'
                file1 = open(path + r.file_names[0], 'rb')
                file2 = open(path + r.file_names[1], 'rb')
                bot.send_document(message.chat.id, file1)
                bot.send_document(message.chat.id, file2)


# polling cycle
if __name__ == '__main__':
    bot.polling(none_stop=True)
