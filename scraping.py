from tinydb import TinyDB, Query
from bs4 import BeautifulSoup
import requests
import urllib.request
import os
import shutil
import re
import pandas as pd
import tabula
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ['BASE_URL']
SCRAPING_URL = os.environ['SCRAPING_URL']
OUTPUT_DIRECTORY = os.environ['OUTPUT_DIRECTORY']


def create_year_month(page_title):
    """yyyymm 形式の年月を取り出す

    Args:
        page_title (str): 

    Returns:
        str: yyyymm形式の文字列
    """
    month_dict = {'1': '01', '2': '02', '3': '03',
                  '4': '04', '5': '05', '6': '06', '7': '07', '8': '08', '9': '09', '10': '10', '11': '11', '12': '12', }

    nendo = re.search('\d*年', page_title)[0].replace('年', '')
    month = re.search('\d*月', page_title)[0].replace('月', '')
    no = None
    try:
        no = re.search('\d*次', page_title)[0].replace('次', '')
    except:
        pass
    # 起点を令和元年の西暦とする
    reiwa_gannen = 2018
    # 令和元年と年度を足して年を出す
    year = reiwa_gannen + int(nendo)
    # 月が1〜3月の場合は翌年になっているのでプラス1年する
    if int(month) < 4:
        year += 1

    # yyyymm文字列を作成
    year_month = str(year) + str(month_dict[month])

    if no is not None:
        year_month = year_month + '_' + str(no)

    return year_month


def download_hoiku_aki_pdf(url):
    """保育園の空き状況PDFの更新をチェックして更新がある場合はPDFをダウンロードします。

    Returns:
        list: ダウンロードした場合はファイルパスを含んだリスト していない場合は空のリスト
    """
    pdf_file_path_list = []
    # 令和四年度の空き状況一覧ページのトップURLにアクセスそてhtml情報取得
    base_url = url
    res = requests.get(base_url)
    html_text = BeautifulSoup(res.text, 'html.parser')

    # 保育園空き状況リンクの取得
    link_list = []
    for link in html_text.select_one('.listlink').select('a[href]'):
        link_list.append(BASE_URL +
                         link.get("href").replace('../', ''))

    # db読み込み
    db = TinyDB('db.json')
    # DBにある情報と空き状況リンクの差集合を見る
    db_data = set(db.all()[0]['urls'])
    link_data = set(link_list)
    url_diff_list = link_data.difference(db_data)

    # 差集合がない場合は終了
    if len(url_diff_list) == 0:
        return pdf_file_path_list

    # 差集合がある場合はリンク先を取得してPDFをダウンロードする
    for diff_url in url_diff_list:
        # PDFリンクが有るページを開く
        pdf_res = requests.get(diff_url)
        # 文字化け対策
        pdf_res.encoding = pdf_res.apparent_encoding
        pdf_html_text = BeautifulSoup(pdf_res.text, 'html.parser')
        # ページタイトルを取得してyyyymmを特定する voice
        page_title = pdf_html_text.select('#voice > h1')[0].text
        year_month = create_year_month(page_title)

        # pdfファイルのリンクを取得
        pdf_url = BASE_URL + \
            pdf_html_text.select_one('.pdf > a[href]').get(
                'href').replace('../', '')
        print(pdf_url)

        # pdfファイル保存名の設定
        save_filename = './temp/' + year_month + '.pdf'
        print(save_filename)
        # PDF保存
        urllib.request.urlretrieve(pdf_url, save_filename)
        # 保存パスの保持
        pdf_file_path_list.append(save_filename)

        # dbデータにURL追加
        db_data.add(diff_url)

    # dbを更新
    db.update({'urls': list(db_data)})
    return pdf_file_path_list


def find_all_files(directory):
    for root, dirs, files in os.walk(directory):
        yield root
        for file in files:
            yield os.path.join(root, file)


def pdf_to_csv(file_path_list):
    out_df_list = []
    # パス下にpdfファイルを走査する
    for file_path in find_all_files('./temp'):
        if '.pdf' not in file_path:
            continue
        # ファイル名を取得する(yyyymm)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        # ファイル名から年を取得
        year = file_name[0:4]
        # ファイル名から月を取得
        month = file_name[4:]
        # pdf読み込みライブラリでPDFを読み込む
        # テーブルの数分のリストを取得する
        df_list = tabula.read_pdf(file_path, pages='all')
        # テーブルの数分のデータフレームが含まれたリストを走査する
        for index, df in enumerate(df_list):
            # 先頭要素は説明用のテーブルなので無視する
            if index == 0:
                continue
            # カラム数を取得する
            # 微妙にフォーマットが違うので差分を吸収するための処理
            len_columns = len(df.columns)
            # カラム数が9の場合
            if len_columns == 9:
                df = df.drop(columns='Unnamed: 5')
                df.columns = ['施設名', '住所', '0歳', '1歳', '2歳', '3歳', '4歳', '5歳']
                df = df[2:]
                df = df.fillna('-')
            # カラム数が8の場合
            elif len_columns == 8:
                # カラムにイレギュラーな値が含まれている場合があるので対応する
                # カラム名にunnamedが含まれている場合
                if 'Unnamed: 0' in df.columns and '受入れ状況' in df.columns:
                    df = df.drop(columns='Unnamed: 0').dropna()
                    sp_df = df['受入れ状況'].str.split(' ', expand=True)
                    sp_df.columns = ['2歳', '3歳']
                    df = df.drop(columns='受入れ状況')
                    df.columns = ['施設名', '住所', '0歳', '1歳', '4歳', '5歳']
                    df = pd.concat([df, sp_df], axis=1)
                else:
                    # カラム名に問題がない場合
                    df.columns = ['施設名', '住所', '0歳',
                                  '1歳', '2歳', '3歳', '4歳', '5歳']
                    df = df.fillna('-')

            df['年'] = year
            df['月'] = month
            out_df_list.append(df)
    con_df = pd.concat(out_df_list)
    con_df.to_csv(OUTPUT_DIRECTORY, mode='a', header=False, index=None)


def update_csv(url):
    try:
        # ディレクトリの指定方法を考える
        # フルパスのほうがいいかも
        os.makedirs('./temp', exist_ok=True)
        path_list = download_hoiku_aki_pdf(url)
        print('scraping end')
        print(path_list)
        if len(path_list) == 0:
            print('no update')
            return
        pdf_to_csv(path_list)
        print('update complete')
    except Exception as e:
        print(e)
    finally:
        print('ok')
        shutil.rmtree('./temp')


# 対象となるURLを引数に渡す
update_csv(SCRAPING_URL)
