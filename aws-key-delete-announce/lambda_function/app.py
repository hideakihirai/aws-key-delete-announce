# ----------------------------------------- #
# 定期的にアクセスキー発行スプレッドシートの利用終了日を検索
# 終了日を過ぎた場合はSlackに通知
# author:hirai
# date:2020/1/6
# ----------------------------------------- #

from __future__ import print_function

# # # sentry
import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
sentry_sdk.init(
    "https://ffb1e61bb27a491baea5a66b1fb9ee77@sentry.io/2005679",
    integrations=[AwsLambdaIntegration()]
    )

import json
import boto3
import urllib.parse
import os
import re
import datetime
import time

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import slackweb
import requests


def get_google_api():
    # Google Driv API認証設定
    SP_CREDNTIAL_FILE = 'My Project 48058-0025e18f407a.json'
    SP_SCOPE = 'https://spreadsheets.google.com/feeds'
    SP_SHEET_KEY = os.environ['SP_SHEET_KEY']  # 環境変数から読み込み
    # sp_sheet_key = "1ZLJf6GQE5ywcATKZxYWWl_EdLjsNHjlCYazrS_DeGcs"

    # スプレッドシートへのアクセス（認証）
    scope = [SP_SCOPE]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(SP_CREDNTIAL_FILE, scope)
    gs_client = gspread.authorize(credentials)
    sp = gs_client.open_by_key(SP_SHEET_KEY)

    return (sp)


def slack_notify(lst):
    # user_id = "ULF3WH04C"    # 【暫定】現状通知対象のIDを固定
    user_id = lst[0]
    msg = "\nアクセスキー発行申請管理者からのお知らせです。" \
          "\nアクセスキー利用終了日まで一週間となりました。" \
          "\n延長が必要な場合は、延長申請をお願いします。"\
          "\n延長されない場合はアクセスキーは自動的に削除されます。" + "\n" + \
          "アカウント名：" + lst[1] + "\n" + \
          "利用目的：" + lst[2] + "\n" + \
          "AWSリソース名：" + lst[3] + "\n" + \
          "アクセスキー利用開始日：" + lst[4] + "\n" + \
          "アクセスキー利用終了日：" + lst[5]

    url = os.environ['SLACK_API_URL']  # 環境変数から読み込み
    # url = "https://slack.com/api/chat.postMessage"

    token = os.environ['BOT_ACCESS_TOKEN']  # 環境変数から読み込み
    # token = "xoxb-10711501747-752648249329-WGXFUDahv2Dyb6Hg3yGDByRm"

    headers = {"Authorization": "Bearer " + token}
    # channel = "<channel or user to alert>"  # ユーザーを指定するとDMが送られる
    params = {
        'channel': user_id,
        'text': msg,
        'as_user': True
    }

    requests.post(url, headers=headers, data=params)
    # requests.post(url, json = {"text":f"<@{id}> {msg}"})


def slack_notify_for_admin(lst, user_id, fullname):
    msg = "\nアクセスキー利用終了日まで一週間の" + fullname + "さんへ通知を行いました。" \
          "\n延長申請がなされない場合は自動的にアカウントを削除します。" + "\n" + \
          "アカウント名：" + lst[1] + "\n" + \
          "利用目的：" + lst[2] + "\n" + \
          "AWSリソース名：" + lst[3] + "\n" + \
          "アクセスキー利用開始日：" + lst[4] + "\n" + \
          "アクセスキー利用終了日：" + lst[5]

    url = os.environ['SLACK_API_URL']  # 環境変数から読み込み
    # url = "https://slack.com/api/chat.postMessage"

    token = os.environ['BOT_ACCESS_TOKEN']  # 環境変数から読み込み
    # token = "xoxb-10711501747-752648249329-WGXFUDahv2Dyb6Hg3yGDByRm"

    headers = {"Authorization": "Bearer " + token}
    # channel = "<channel or user to alert>"  # ユーザーを指定するとDMが送られる
    params = {
        'channel': user_id,
        'text': msg,
        'as_user': True
    }

    requests.post(url, headers=headers, data=params)
    # requests.post(url, json = {"text":f"<@{id}> {msg}"})


def slack_notify_for_nouser(user_id, fullname):
    msg = "\nアクセスキー発行申請管理者からのお知らせです。"\
          "\nユーザーへSlack通知実施時に、" \
           + fullname + "さんのユーザー情報が見つかりませんでした。" \
          "\nスプレッドシートのusers_json情報を更新してください。"

    url = os.environ['SLACK_API_URL']  # 環境変数から読み込み
    # url = "https://slack.com/api/chat.postMessage"

    token = os.environ['BOT_ACCESS_TOKEN']  # 環境変数から読み込み
    # token = "xoxb-10711501747-752648249329-WGXFUDahv2Dyb6Hg3yGDByRm"

    headers = {"Authorization": "Bearer " + token}
    # channel = "<channel or user to alert>"  # ユーザーを指定するとDMが送られる
    params = {
        'channel': user_id,
        'text': msg,
        'as_user': True
    }

    requests.post(url, headers=headers, data=params)
    # requests.post(url, json = {"text":f"<@{id}> {msg}"})


def detach_iam_user_policy(iam_name, policy_arn):
    return (
        boto3.client("iam").detach_user_policy(
            UserName=iam_name,
            PolicyArn=policy_arn
        ))

def delete_iam_user(iam_name):
    return (
        boto3.client("iam").delete_user(
            UserName=iam_name,
        ))

def delete_iam_policy(policy_arn):
    return (
        boto3.client("iam").delete_policy(
            PolicyArn=policy_arn
        ))

def delete_iam_access_key(iam_name, access_key_id):
    return (
        boto3.client("iam").delete_access_key(
            UserName=iam_name,
            AccessKeyId=access_key_id
        ))


# 以下lambda_function()関数内部
def lambda_handler(event, context):
    # initial
    user_id = ""

    # set date
    nowdatetime = datetime.datetime.today()  # 今日の日付
    nowdate = nowdatetime.date()
    one_week_ago = nowdate + datetime.timedelta(days=7)  # 一週間前
    next_day = nowdate - datetime.timedelta(days=1)  # 次の日

    # google_spreadsheet_api
    sp = get_google_api()
    SP_SHEET = os.environ['SP_SHEET']  # 環境変数から読み込み
    wks = sp.worksheet(SP_SHEET)

    values = wks.get_all_values()  # 全情報をvaluesに配列として入れ込む

    for row, name in enumerate(values, start=0):  # セル内容の取得
        if row == 0:
            continue

        # get cell value for spreadsheet(date)
        end_day = values[row][8]  # アクセスキー利用終了日セルデータを取得する
        full_name = values[row][1]  # 氏名セルデータを取得
        status = values[row][10]  # アカウントの状態
        access_key_id = values[row][11]  # アクセスキーID

        # exchenge datetime (from str to datetime)
        strdatetime = end_day.replace("/", "")  # /を""置き換えで無くす
        impdatetime = datetime.datetime.strptime(strdatetime, "%Y%m%d")  # datetime形式に変換
        impdate = impdatetime.date()  # date形式に変換

        # compare one_week_ago vs import_date_value
        if not (re.search("削除", status) or re.search("延長", status)) \
                and one_week_ago == impdate:  # 状態が削除もしくは延長でなく、残り一週間の場合
            # get cell value for user_json
            sp_sheet_tbl = os.environ['SP_SHEET_TBL']  # 環境変数から読み込み
            # sp_sheet_tbl = "users_json"                         # シート名設定
            wks_tbl = sp.worksheet(sp_sheet_tbl)  # 名前テーブルシートへアクセス

            values_tbl = wks_tbl.get_all_values()  # 全情報をvalues_tblに配列として入れ込む

            for row2, name2 in enumerate(values_tbl, start=0):  # 名前シートからセル内容の取得
                last_name = values_tbl[row2][3]
                first_name = values_tbl[row2][4]

                if last_name == "" or first_name == "":
                    user_id = "none"
                elif last_name in full_name and first_name in full_name:
                    lst = []
                    user_id = values_tbl[row2][0]  # ユーザーID
                    obj = values[row][2]  # 申請目的・理由
                    resource = values[row][4]  # AWSサービス名
                    start_day = values[row][7]  # アクセスキー利用開始日
                    account = values[row][9]  # アカウント名
                    lst = [user_id, account, obj, resource, start_day, end_day]

                    # to slack
                    slack_notify(lst)
                    admin_id_1 = os.environ['ADMIN_ID_1']   # 【暫定】現状通知対象のIDを固定
                    slack_notify_for_admin(lst, admin_id_1, full_name)
                    admin_id_2 = os.environ['ADMIN_ID_2']   # 【暫定】現状通知対象のIDを固定
                    slack_notify_for_admin(lst, admin_id_2, full_name)
                    break
                else:
                    user_id = "none"

            # ユーザーが見つからなかった場合の通知
            if user_id == "none":
                admin_id_1 = os.environ['ADMIN_ID_1']  # 【暫定】現状通知対象のIDを固定
                slack_notify_for_nouser(admin_id_1, full_name)
                admin_id_2 = os.environ['ADMIN_ID_2']  # 【暫定】現状通知対象のIDを固定
                slack_notify_for_nouser(admin_id_2, full_name)

        elif not (re.search("削除", status) or re.search("延長", status)) \
                and next_day == impdate:  # 状態が削除もしくは延長でなく、終了日を過ぎている場合
            # アカウントを削除する
            account = values[row][9]  # アカウント名
            arn = "arn:aws:iam::729700637718:policy/"
            policy_arn = arn + account
            # detach
            detach_iam_user_policy(account, policy_arn)

            # detachした後スリープいるかも
            time.sleep(5)

            # delete
            delete_iam_access_key(account, access_key_id)
            delete_iam_user(account)
            delete_iam_policy(policy_arn)

            # 状態列に「削除済み」を記載する
            wks.update_cell(row + 1, 11, "削除済み")
        else:
            pass

    print("end_function")