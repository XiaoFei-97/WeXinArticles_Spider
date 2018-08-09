from urllib.parse import urlencode
import pymongo
import requests
from lxml.etree import XMLSyntaxError
from requests.exceptions import ConnectionError
from pyquery import PyQuery as pq
from config import *

# 定义一个MongoDB本地客户端
client = pymongo.MongoClient(MONGO_URI)
# 在本地客户端创建一个数据库
db = client[MONGO_DB]

base_url = 'http://weixin.sogou.com/weixin?'

headers = {
    'Cookie': 'SUID=F6177C7B3220910A000000058E4D679; SUV=1491392122762346; ABTEST=1|1491392129|v1; SNUID=0DED8681FBFEB69230E6BF3DFB2F8D6B; ld=OZllllllll2Yi2balllllV06C77lllllWTZgdkllll9lllllxv7ll5@@@@@@@@@@; LSTMV=189%2C31; LCLKINT=1805; weixinIndexVisited=1; SUIR=0DED8681FBFEB69230E6BF3DFB2F8D6B; JSESSIONID=aaa-BcHIDk9xYdr4odFSv; PHPSESSID=afohijek3ju93ab6l0eqeph902; sct=21; IPLOC=CN; ppinf=5|1491580643|1492790243|dHJ1c3Q6MToxfGNsaWVudGlkOjQ6MjAxN3x1bmlxbmFtZToyNzolRTUlQjQlOTQlRTUlQkElODYlRTYlODklOER8Y3J0OjEwOjE0OTE1ODA2NDN8cmVmbmljazoyNzolRTUlQjQlOTQlRTUlQkElODYlRTYlODklOER8dXNlcmlkOjQ0Om85dDJsdUJfZWVYOGRqSjRKN0xhNlBta0RJODRAd2VpeGluLnNvaHUuY29tfA; pprdig=j7ojfJRegMrYrl96LmzUhNq-RujAWyuXT_H3xZba8nNtaj7NKA5d0ORq-yoqedkBg4USxLzmbUMnIVsCUjFciRnHDPJ6TyNrurEdWT_LvHsQIKkygfLJH-U2MJvhwtHuW09enCEzcDAA_GdjwX6_-_fqTJuv9w9Gsw4rF9xfGf4; sgid=; ppmdig=1491580643000000d6ae8b0ebe76bbd1844c993d1ff47cea',
    'Host': 'weixin.sogou.com',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36'
}

proxy = None


def get_proxy():
    """
        作用：从代理池中获取一个代理IP
    """
    try:
        # 运行代理池，从Flask网页中读取IP
        response = requests.get(PROXY_POOL_URL)
        if response.status_code == 200:
            return response.text
        # 如果状态码不是200,也返回None
        return None
    except ConnectionError:
        return None

def get_html(url, count=1):
    """
        作用：通过代理访问与正常访问来回切换，获得页面源码
        url: 需要返回的页面url地址
        count: 捕获异常次数，即错误尝试，默认为1
    """
    print('Crawling', url)
    print('Trying Count', count)
    # 定义一个proxy的全局变量
    global proxy
    # 判断count次数是否超过最大次数，就返回None
    if count >= MAX_COUNT:
        print('Tried Too Many Counts')
        return None
    try:
        # 判断是否从代理池中拿到proxy代理
        if proxy:
            proxies = {
                'http': 'http://' + proxy
            }
            # 使用代理访问，allow_redirects=False表示关闭默认的重定向跳转
            response = requests.get(url, allow_redirects=False, headers=headers, proxies=proxies)
        else:
            # 没有拿到代理则使用正常IP访问
            response = requests.get(url, allow_redirects=False, headers=headers)
        if response.status_code == 200:
            return response.text
        if response.status_code == 302:
            # Need Proxy
            print('302')
            # 页面出现302状态码后，重新获取一个代理IP，并使用这个IP
            proxy = get_proxy()
            if proxy:
                print('Using Proxy', proxy)
                # 递归调用当前函数获取页面源码
                return get_html(url)
            else:
                print('Get Proxy Failed')
                return None
    except ConnectionError as e:
        print('Error Occurred', e.args)
        proxy = get_proxy()
        # 捕获到异常，错误尝试次数+1，超过规定次数就退出当前if语句执行
        count += 1
        return get_html(url, count)



def get_index(keyword, page):
    """
        作用： 主要是调用get_html函数，实现与get_html函数功能相同
        keyword: 搜索的关键字
        page：访问的页码
    """
    data = {
        'query': keyword,
        'type': 2,
        'page': page
    }
    # 将get的参数进行转码
    queries = urlencode(data)
    url = base_url + queries
    html = get_html(url)
    return html

def parse_index(html):
    """
        作用：使用pyquery库对网页进行解析，并提取文章的a标签跳转url
        html： 网页源码，即通过get_index函数获得
    """
    doc = pq(html)
    items = doc('.news-box .news-list li .txt-box h3 a').items()
    for item in items:
        yield item.attr('href')

def get_detail(url):
    """
        作用： 获取每篇文章的详情页网页源码
        url： 详情页url地址
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except ConnectionError:
        return None

def parse_detail(html):
    """
        作用： 对每篇文章的详情页进行解析，使用pyqery库对网页进行解析
        html: 详情页的网页源码，通过get_detail函数获得 
    """
    try:
        doc = pq(html)
        title = doc('.rich_media_title').text()
        content = doc('.rich_media_content').text()
        date = doc('#post-date').text()
        nickname = doc('#js_profile_qrcode > div > strong').text()
        wechat = doc('#js_profile_qrcode > div > p:nth-child(3) > span').text()
        return {
            'title': title,
            'content': content,
            'date': date,
            'nickname': nickname,
            'wechat': wechat
        }
    except XMLSyntaxError:
        return None

def save_to_mongo(data):
    """
        作用： 将详情页解析的数据存储在MongoDB中
        data： 需要存储的数据
    """
    # 判断存储数据是否发生更新
    if db['articles'].update({'title': data['title']}, {'$set': data}, True):
        print('Saved to Mongo', data['title'])
    else:
        print('Saved to Mongo Failed', data['title'])


def main():
    # 通过cookie访问100页
    for page in range(1, 101):
        # 加入keyword即page参数，获得文章列表源码
        html = get_index(KEYWORD, page)
        if html:
            # 对文章列表进行解析，拿到每篇文章的url地址
            article_urls = parse_index(html)
            for article_url in article_urls:
                # 使用get_detail函数访问每篇文章详情页地址
                article_html = get_detail(article_url)
                if article_html:
                    # 解析每篇文章详情页数据
                    article_data = parse_detail(article_html)
                    print(article_data)
                    if article_data:
                        # 保存至MongoDB数据库
                        save_to_mongo(article_data)



if __name__ == '__main__':
    main()
