import telebot
import datetime
import sqlite3
import requests
import time
import logging
import os
from transliterate import translit as tr
from telebot import types

import constants
import config
from m1_req import main_func
from m1_req import main_place
from m1_req import hello_back
from m1_speechkit import speech_to_text
from m1_speechkit import SpeechException
from m2_main import M2Retrieving
from m3_main import M3Visualizing

API_TOKEN = config.TELEGRAM_API_TOKEN_FINAL
bot = telebot.TeleBot(API_TOKEN)

logging.basicConfig(filename='logs.log', level=50, format='%(asctime)s\t%(message)s', datefmt='%Y-%m-%d %H:%M')


# checks if the string may be converted into integer
def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


# /cr command handler
@bot.message_handler(commands=['cr'])
def send_welcome(message):
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE userid = ' + str(message.chat.id))
    data = cursor.fetchall()  # gets sql row from the table 'users'
    if len(data) != 0:
        s = str(message.text)[4:]  # cut symbols "/cr " off
        if s == '' or main_place(s) is not None:
            if s == '':  # in case of empty space after /cr null will be written into the table
                cursor.execute('UPDATE users SET place=\'' + 'null' + '\' WHERE userid=' + str(message.chat.id) + ';')
                connection.commit()
                connection.close()

            # otherwise string will be edited in the parser and then will be written to the table
            if main_place(s) is not None:
                s = main_place(s)
                cursor.execute('UPDATE users SET place=\'' + s + '\' WHERE userid=' + str(message.chat.id) + ';')
                connection.commit()
                connection.close()

            con = sqlite3.connect('users.db')
            cursor = con.cursor()
            cursor.execute('SELECT * FROM users WHERE userid = ' + str(message.chat.id))
            data = cursor.fetchall()
            con.close()
            final_result_formatting(data, message)
        else:
            bot.send_message(message.chat.id, constants.ERROR_NO_UNDERSTANDING)
    else:
        bot.send_message(message.chat.id, constants.ERROR_CR_MSG)


# /start command handler; send start-message to the user
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, constants.START_MSG, parse_mode='HTML')


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
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE userid = ' + str(message.chat.id))
    data = cursor.fetchall()

    if len(data) != 0:
        cursor.execute(
            # delete previous info about user's call from the table
            'DELETE FROM users WHERE userid = ' + str(message.chat.id))
        connection.commit()
        connection.close()

    # TODO: abstraction7
    s = message.text[8:]
    if s == '':  # if there's no text after /search, start questioning user w/ buttons
        # TODO: abstraction8
        markup = types.ReplyKeyboardMarkup()
        markup.row('доходы')
        markup.row('расходы')
        markup.row('дефицит/профицит')
        bot.send_message(message.chat.id, constants.MSG_BEFORE_THEMES, reply_markup=markup)
        connection = sqlite3.connect('users.db')
        cursor = connection.cursor()
        s_main = 'INSERT INTO users (id, userid, subject, place, year, sector, planned_or_actual, thm) VALUES(NULL, ' + \
                 str(message.chat.id) + ', \'' + str(0) + '\', \'' + str(0) + '\', \'' + str(0) + '\', \'' + str(
            0) + '\', \'' + str(0) + '\', \'' + str(0) + '\')'
        cursor.execute(s_main)
        connection.commit()
        connection.close()

    else:
        # parse message after the /search command and pass it further
        s1 = main_func(s.lower())
        asked_question = s.lower()
        logging.critical("{}\t{}".format(message.chat.id, asked_question))
        s_mod2 = forming_string_from_neural(s1)
        querying_and_visualizing(message, s_mod2)


# Text handler | PRESSING NON-INLINE BUTTONS RETURNS TEXT TOO!
@bot.message_handler(content_types=['text'])
def repeat_all_messages(message):
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE userid = ' + str(message.chat.id))
    data = cursor.fetchall()
    k = 0
    for i in data:
        for i1 in i:
            if i1 == '0':
                k += 1

    now_date = datetime.date.today()

    # check if user wants us to salute him
    if hello_back(message.text) is not None:
        bot.send_message(message.chat.id, hello_back(message.text))

    # Processing of all the words...
    elif represents_int(message.text) and len(data) != 0:
        i = int(message.text)
        markup = types.ReplyKeyboardHide()
        if 2006 < i <= now_date.year:
            # Processing 2016 year
            if i == 2016:
                i = 'null'

            cursor.execute('UPDATE users SET year=' + str(i) + ' WHERE userid=' + str(message.chat.id) + ';')
            connection.commit()
            connection.close()
            cr_markup(message)

        else:
            current_year = str(datetime.datetime.now().year)
            bot.send_message(message.chat.id, constants.ERROR_NO_DATA_THIS_YEAR % current_year, reply_markup=markup)

    # TODO: abstraction9
    elif (message.text == 'доходы' or message.text == 'расходы' or message.text == 'дефицит/профицит'
          or message.text == 'налоговые' or message.text == 'неналоговые' or message.text == 'все') and (
                len(data) != 0):
        k = message.text
        if message.text == 'доходы' or message.text == 'расходы' or message.text == 'дефицит/профицит':
            cursor.execute('UPDATE users SET subject=\'' + str(k) + '\' WHERE userid=' + str(message.chat.id) + ';')
            connection.commit()
            connection.close()
        if message.text == 'налоговые' or message.text == 'неналоговые' or message.text == 'все':
            if message.text == 'все':
                k_clone = 'null'
            elif message.text == 'налоговые':
                k_clone = 'налоговый'
            else:
                k_clone = 'неналоговый'
            cursor.execute(
                'UPDATE users SET planned_or_actual=\'' + k_clone + '\' WHERE userid=' + str(message.chat.id) + ';')
            connection.commit()
            connection.close()
        if k == 'расходы':
            bot.send_message(
                message.chat.id, constants.MSG_BEFORE_SPHERE,
                parse_mode='HTML',
                reply_markup=constants.SPHERE_KEYBOARD)

            markup = types.ReplyKeyboardMarkup()
            markup.row('текущие')
            markup.row('фактические')
            markup.row('плановые')
            bot.send_message(message.chat.id, constants.MSG_BEFORE_TYPE_EXPENDITURES, reply_markup=markup)
        elif k == 'дефицит/профицит' or k == 'налоговые' or k == 'неналоговые' or k == 'все':
            markup = types.ReplyKeyboardMarkup()
            if k == 'дефицит/профицит':
                markup.row('текущий')
                markup.row('фактический')
                markup.row('плановый')
            else:
                markup.row('текущие')
                markup.row('фактические')
                markup.row('плановые')
            bot.send_message(message.chat.id, constants.MSG_BEFORE_TYPE_PROFIT, reply_markup=markup)
        elif k == 'доходы':
            markup = types.ReplyKeyboardMarkup()
            markup.row('все')
            markup.row('налоговые')
            markup.row('неналоговые')
            bot.send_message(message.chat.id, constants.MSG_BEFORE_NALOG_NENALOG, reply_markup=markup)

    elif (message.text == 'фактические' or message.text == 'фактический' or
                  message.text == 'плановые' or message.text == 'плановый' or
                  message.text == 'текущие' or message.text == 'текущий' or
                  message.text == 'все') and (len(data) != 0):
        k = 0
        if message.text == 'фактические' or message.text == 'фактический':
            k = 'фактический'

            year_markup(message)

            cursor.execute(
                'UPDATE users SET sector=\'' + str(k) + '\' WHERE userid=' + str(message.chat.id) + ';')
            connection.commit()
            connection.close()

        if message.text == 'плановые' or message.text == 'плановый':
            if message.text == 'плановые':
                k = 'плановый'
            elif message.text == 'плановый':
                k = message.text

            year_markup(message)

            cursor.execute(
                'UPDATE users SET sector=\'' + str(k) + '\' WHERE userid=' + str(message.chat.id) + ';')

            connection.commit()
            connection.close()

        if message.text == 'текущие' or message.text == 'текущий':
            markup = types.ReplyKeyboardHide()
            k = 'текущий'
            cursor.execute(
                'UPDATE users SET sector=\'' + str(k) + '\' WHERE userid=' + str(message.chat.id) + ';')
            cursor.execute(
                'UPDATE users SET year=' + 'null' + ' WHERE userid=' + str(message.chat.id) + ';')
            connection.commit()
            connection.close()
            cr_markup(message)

    elif (message.text == 'Россия'
          or message.text == 'Москва'
          or message.text == 'Московская область'
          or message.text == 'Федеральный бюджет'):
        if message.text == 'Федеральный бюджет':
            cursor.execute('UPDATE users SET place=\'' + 'null' + '\' WHERE userid=' + str(message.chat.id) + ';')
            cursor.execute('SELECT * FROM users WHERE userid = ' + str(message.chat.id))
            data = cursor.fetchall()
            connection.commit()
            connection.close()
        elif (message.text == 'Россия'
              or message.text == 'Москва'
              or message.text == 'Московская область'):
            s = main_place(message.text.lower())
            cursor.execute('UPDATE users SET place=\'' + s + '\' WHERE userid=' + str(message.chat.id) + ';')
            cursor.execute('SELECT * FROM users WHERE userid = ' + str(message.chat.id))
            data = cursor.fetchall()
            connection.commit()
            connection.close()

        final_result_formatting(data, message)

    elif message.text == 'null':
        cursor.execute('UPDATE users SET place=\'' + 'null' + '\' WHERE userid=' + str(message.chat.id) + ';')
        connection.commit()
        connection.close()

    elif message.text == 'Другие':
        markup = types.ReplyKeyboardHide()
        bot.send_message(message.chat.id, constants.TERRITORY_MSG, reply_markup=markup)

    else:
        bot.send_message(message.chat.id, constants.ERROR_CHECK_INPUT)


# inline mode handler
@bot.inline_handler(lambda query: len(query.query) >= 0)
def query_text(query):
    input_message_content = query.query
    s1 = main_func(input_message_content)
    s_mod2 = forming_string_from_neural(s1)  # receive Module 2-friendly string format
    print(s_mod2)
    result_array = []
    result = M2Retrieving.get_data(s_mod2)  # check if current user string is correct
    if result.status is False:  # in case the string is not correct we ask user to keep typing
        msg = types.InlineQueryResultArticle(id='0',
                                             title='Продолжайте ввод запроса',
                                             input_message_content=types.InputTextMessageContent(
                                                 message_text=input_message_content + '\nЗапрос не удался😢'
                                             ))
        result_array.append(msg)  # Nothing works without this list, I dunno why :P
        bot.answer_inline_query(query.id, result_array)

    else:
        logging.critical("{}\t{}".format("inline", input_message_content))
        m3_result = M3Visualizing.create_response(query.id, result.response, result.theme, visualization=False)
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


# inline messages query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    # TODO: abstraction10
    if call.message:
        connection = sqlite3.connect('users.db')
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM users WHERE userid = ' + str(call.message.chat.id))
        data = cursor.fetchall()
        if call.data == '2':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Общегосударственные вопросы"')
        elif call.data == '3':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Национальную оборону"')
        elif call.data == '4':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Национальную безопасность и правоохранительные органы"')
        elif call.data == '5':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Национальную экономику"')
        elif call.data == '6':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "ЖКХ"')
        elif call.data == '7':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Защиту окружающей среды"')
        elif call.data == '8':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Образование"')
        elif call.data == '9':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Культуру"')
        elif call.data == '10':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Здравоохранение"')
        elif call.data == '11':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Социальную политику"')
        elif call.data == '12':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + call.data + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Спорт и физическую культуру"')
        elif call.data == '13':
            if len(data) != 0:
                cursor.execute('UPDATE users SET thm=\'' + 'null' + '\' WHERE userid=' + str(
                    call.message.chat.id) + ';')
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Вы выбрали "Расходы в целом"')
        elif call.data == 'full_documentation':
            file1 = open('Datatron User Guide.pdf', 'rb')
            bot.send_document(chat_id=call.message.chat.id,
                              data=file1)
        elif call.data == 'intro_video':
            bot.send_message(call.message.chat.id, 'https://youtu.be/swok2pcFtNI')
        connection.commit()
        connection.close()


# voice message handler
@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()
    cursor.execute(
        'DELETE FROM users WHERE userid = ' + str(message.chat.id))
    connection.commit()
    connection.close()

    file_info = bot.get_file(message.voice.file_id)
    file = requests.get(
        'https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
    try:
        text = speech_to_text(bytes=file.content)
        logging.critical("{}\t{}".format(message.chat.id, text))
    except SpeechException:
        msg = constants.ERROR_CANNOT_UNDERSTAND_VOICE
        bot.send_message(message.chat.id, msg)
    else:
        s1 = main_func(text)
        s_mod2 = forming_string_from_neural(s1)
        querying_and_visualizing(message, s_mod2)


def year_markup(message):
    # TODO: abstraction11
    markup = types.ReplyKeyboardMarkup(row_width=4)
    y2007 = types.KeyboardButton('2007')
    y2008 = types.KeyboardButton('2008')
    y2009 = types.KeyboardButton('2009')
    y2010 = types.KeyboardButton('2010')
    y2011 = types.KeyboardButton('2011')
    y2012 = types.KeyboardButton('2012')
    y2013 = types.KeyboardButton('2013')
    y2014 = types.KeyboardButton('2014')
    y2015 = types.KeyboardButton('2015')
    y2016 = types.KeyboardButton('2016')
    markup.row(y2007, y2008, y2009)
    markup.row(y2010, y2011, y2012)
    markup.row(y2013, y2014, y2015)
    markup.row(y2016)
    bot.send_message(message.chat.id, constants.YEAR_MSG, reply_markup=markup, )


def cr_markup(message):
    markup = types.ReplyKeyboardMarkup()
    null_b = types.KeyboardButton('Федеральный бюджет')
    russia_b = types.KeyboardButton('Россия')
    moscow_b = types.KeyboardButton('Москва')
    m_region_b = types.KeyboardButton('Московская область')
    other_b = types.KeyboardButton('Другие')
    markup.row(null_b, russia_b)
    markup.row(moscow_b, m_region_b)
    markup.row(other_b)
    bot.send_message(message.chat.id, 'Выберите территорию:', reply_markup=markup)


def file_naming(request_string):
    request_string = tr(request_string, 'ru', reversed=True)
    filename = request_string.replace('null', '')
    filename = filename.replace(',', '_')

    for i in range(0, 3):
        filename = filename.replace('__', '_')

    if filename[len(filename) - 1] == '_':
        filename = filename[:len(filename) - 1]

    print(filename)

    filename_svg = 'diagram_' + filename + '.svg'
    filename_pdf = 'table_' + filename + '.pdf'
    names = [filename_svg, filename_pdf]
    return names


def forming_string_from_neural(s1):
    s_mod2 = ''
    if s1[0] == 'расходы':
        s_mod2 += s1[0] + ',' + s1[4] + ',' + 'null' + ',' + str(s1[2]) + ',' + str(s1[3]) + ',' + s1[1]
    elif s1[0] == 'доходы':
        s_mod2 += s1[0] + ',' + s1[4] + ',' + str(s1[3]) + ',' + str(s1[2]) + ',' + 'null' + ',' + s1[1]
    elif s1[0] == 'дефицит':
        s_mod2 += s1[0] + ',' + s1[4] + ',' + 'null' + ',' + str(s1[2]) + ',' + 'null' + ',' + s1[1]
    return s_mod2


def querying_and_visualizing(message, s_mod2, notify_user=True):
    markup = types.ReplyKeyboardHide()
    print(s_mod2)
    try:
        m2_result = M2Retrieving.get_data(s_mod2)
        if m2_result.status is False:
            bot.send_message(message.chat.id, m2_result.message, reply_markup=markup)
        else:
            bot.send_message(message.chat.id, constants.MSG_WE_WILL_FORM_DATA_AND_SEND_YOU, reply_markup=markup)
            names = file_naming(s_mod2)
            m3_result = M3Visualizing.create_response(message.chat.id, m2_result.response, m2_result.theme,
                                                      filename_svg=names[0], filename_pdf=names[1])
            if m3_result.data is False:
                bot.send_message(message.chat.id, constants.ERROR_NULL_DATA_FOR_SUCH_REQUEST_LONG)
            else:
                # Informing user how system understood him in case of voice and text processing
                if notify_user is True:
                    bot.send_message(message.chat.id, m2_result.message)

                if m3_result.is_file is False:
                    bot.send_message(message.chat.id, m3_result.number)
                else:
                    path = m3_result.path + '\\'
                    bot.send_message(message.chat.id, m3_result.number)
                    file1 = open(path + names[0], 'rb')
                    file2 = open(path + names[1], 'rb')
                    bot.send_document(message.chat.id, file1)
                    bot.send_document(message.chat.id, file2)
    except:
        bot.send_message(message.chat.id, constants.ERROR_SERVER_DOES_NOT_RESPONSE)


# forms string for Module 2
def final_result_formatting(data, message):
    # count data collected from the 'user' table
    k = 0
    for i in data:
        for i1 in i:
            if i1 == '0':
                k += 1
    if k > 2:
        bot.send_message(message.chat.id, constants.ERROR_NOT_FULL_INFO, reply_markup=types.ReplyKeyboardHide())
    else:
        connection = sqlite3.connect('users.db')
        cursor = connection.cursor()
        s_main = 'INSERT INTO users (id, userid, subject, place, year, sector, planned_or_actual, thm) VALUES(NULL, ' + \
                 str(message.chat.id) + ', \'' + str(0) + '\', \'' + str(0) + '\', \'' + str(
            0) + '\', \'' + str(
            0) + '\', \'' + str(0) + '\', \'' + str(0) + '\')'
        cursor.execute(s_main)
        connection.commit()
        connection.close()

        new_data = []
        count = 0
        while count <= 7:
            for item in data:
                new_data.append(item[count])
                count += 1

        # format string for Module 2
        # TODO: abstraction12
        for n, i in enumerate(new_data):
            if i == 0 or i == '0' or i is None:
                new_data[n] = 'null'
            if i == 'дефицит/профицит':
                new_data[n] = 'дефицит'

        new_data[3] = new_data[3].lower()
        s_mod2, filename1, filename2 = '', '', ''
        s_mod2 += str(new_data[2]) + ',' + str(new_data[5]) + ',' + str(new_data[6]) + ',' + str(
            new_data[4]) + ',' + str(
            new_data[7]) + ',' + str(new_data[3])

        querying_and_visualizing(message, s_mod2)


# polling cycle
if __name__ == '__main__':

    # admin_id = (65305591, 164241807, 139653713)
    #
    # for _id in admin_id:
    #     bot.send_message(_id, "ADMIN_INFO: Бот запушен")
    #
    e = None
    count = 0

    while True:
        try:
            # No more than 5 attempts for one exception
            if count < 900:
                count += 1
                bot.polling(none_stop=True)
            else:
                # err_message = "ADMIN_INFO: Бот упал.\n\nERROR: '{}'.".format(e)
                # for _id in admin_id:
                #     bot.send_message(_id, err_message)
                break
        except Exception as e1:
            os.popen("ipconfig /flushdns")
            print('There was requests.exceptions.ConnectionError')
            print(type(e1),type(e))
            print(count)
            #if type(e) == type(e1) and e.args is e1.args:
            if type(e) is type(e1):
                time.sleep(10)
            else:
                e = e1
                count = 0
            print(count)
