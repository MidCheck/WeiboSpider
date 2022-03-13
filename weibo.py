from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

from wb_data import WbData
import re, time, logging
from datetime import datetime

class WeiboSpider:
    base_url = "https://weibo.com/"
    search_url = "https://s.weibo.com/weibo?q="

    def __init__(self, chromedriver_path: str, comments_path: str, debug_port: int=9222, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.service = Service(chromedriver_path)
        self.options = webdriver.ChromeOptions()
        self.options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        self.driver = webdriver.Chrome(service=self.service, options=self.options)
        self.db = WbData("users.sqlite", comments_path)
    
    def __del__(self):
        self.db.close()
    
    def parse_avator(self, parent: WebElement, feed: dict):
        try:
            avator_elem = parent.find_element(By.CLASS_NAME, 'avator')
        except NoSuchElementException:
            self.log.warning("[-] card [%s](%s) not has avator" % (feed['mid'], self.driver.current_url))
        else:
            try:
                user_link_elem = avator_elem.find_element(By.TAG_NAME, "a")
                user_link = user_link_elem.get_attribute('href')
            except NoSuchElementException:
                self.log.warning("[-] card [%s](%s) not has user link" % (feed['mid'], self.driver.current_url))
            else:
                if matched := re.findall('https://weibo.com/(\d+)?.*', user_link):
                    feed['uid'] = matched[0]
            try:
                img_elem = avator_elem.find_element(By.TAG_NAME, "img")
            except NoSuchElementException:
                self.log.warning("[-] card [%s](%s) not has user avator" % (feed['mid'], self.driver.current_url))
            else:
                src = img_elem.get_attribute('src')
                feed['avator'] = src
    
    def parse_info(self, card_feed: WebElement, feed: dict):
        try:
            name_elem = card_feed.find_element(By.CLASS_NAME, "name")
        except NoSuchElementException:
            self.log.warning("[-] card [%s](%s) not has nick_name" % (feed['mid'], self.driver.current_url))
        else:
            nick_name = name_elem.get_attribute("nick-name")
            feed['nick_name'] = nick_name

    def parse_from(self, card_feed: WebElement, feed: dict):
        try:
            from_elem = card_feed.find_element(By.CLASS_NAME, 'from')
        except NoSuchElementException:
            self.log.warning("[-] card [%s](%s) not has nofollow" % (feed['mid'], self.driver.current_url))
        else:
            link_elems: list = from_elem.find_elements(By.TAG_NAME, "a")
            if len(link_elems) > 1:
                last_elem = link_elems.pop()
                feed['from'] = last_elem.text
            else:
                feed['from'] = ''

    def parse_new_tab(self, feed: dict):
        try:
            info_time_elem = self.driver.find_element(By.XPATH, f'//a[contains(@class, "head-info_time")]')
        except NoSuchElementException:
            self.log.warning("[-] [%s](%s) not has info time" % (self.driver.current_url, feed['mid']))
        else:
            feed['time'] = info_time_elem.text

        try:
            # get weibo content
            wbtext_elem = self.driver.find_element(By.XPATH, '//div[starts-with(@class, "detail_wbtext_")]')
        except NoSuchElementException:
            self.log.warning("[-] [%s](%s) not has detail webtext" % (self.driver.current_url, feed['mid']))
        else:
            feed['content'] = wbtext_elem.text

        # get weibo comments
        feed['comments'] = { 'set': set(), 'comms': list(), 'finish': None }
        self.new_tab_comments(feed['comments'])

    def new_tab_comments(self, comments: dict):
        self.driver.execute_script('window.scrollBy(0, document.body.scrollHeigth)')
        is_finish = False
        comments_set = set()
        sentinel_time  = time.time()
        last_time = sentinel_time
        time_distance1 = 60
        time_distance2 = 120
        while not is_finish:
            try:
                items = self.driver.find_elements(By.CLASS_NAME, "vue-recycle-scroller__item-view")
            except NoSuchElementException:
                self.log.warning("[-] [%s] not has detail comments" % (self.driver.current_url))
                break
            else:
                if comments['finish'] is not None or len(items) == 0:
                    is_finish = True
                for item in items:
                    try:
                        comm_res = re.findall(r"(.*)\s?:(.*)\s((?:\d{,2}\-?){3}\s?(?:\d{1,2}:\d{1,2}))\s?", item.text)
                        if not comm_res:
                            continue
                        hash_str = ''.join([comm_res[0][0], comm_res[0][1], comm_res[0][2]])
                        if hash_str in comments_set:
                            continue
                        comments_set.add(hash_str)
                        scroller_elem: WebElement = item.find_element(By.CLASS_NAME, "wbpro-scroller-item")
                        data_index = int(scroller_elem.get_attribute("data-index"))
                        avator_elem: WebElement = item.find_element(By.CLASS_NAME, "woo-avatar-img")
                        avator = avator_elem.get_attribute('src')
                        comments['set'].add(data_index)
                        is_finish = False
                        sentinel_time = time.time()
                        last_time = sentinel_time
                    except NoSuchElementException as e:
                        self.log.warning("[-] [%s] has no wbpro-scroller-item: %s" % (self.driver.current_url, str(e)))
                    except ValueError as e:
                        self.log.warning("[-] [%s] has value error: %s" % (self.driver.current_url, str(e)))
                    else:
                        try:
                            uid = ''
                            uid_elem = scroller_elem.find_element(By.TAG_NAME, "a")
                            if res := re.findall("/u/(\d+)", uid_elem.get_attribute('href')):
                                uid = res[0]
                        except NoSuchElementException:
                            pass
                        finally:
                            for nick_name, comment_content, comment_time in comm_res:
                                comments['comms'].append((uid, nick_name, avator, comment_time, comment_content))
            finally:
                try:
                    bottom_elem = self.driver.find_element(By.XPATH, "//div[starts-with(@class, 'Bottom_text_')]")
                except NoSuchElementException:
                    try:
                        if es := self.driver.find_elements(By.XPATH, "//span[@class='woo-tip-text']"):
                            for e in es:
                                if e.text.find("加载失败") > 0:
                                    try:
                                        e.click()
                                    except Exception:
                                        pass
                                    else:
                                        time.sleep(1)
                                    break
                                elif e.text.find("发表你的评论或") > 0:
                                    comments['finish'] = e.text
                                    is_finish = True
                                    break
                    except NoSuchElementException:
                        pass
                    finally:
                        self.driver.execute_script('window.scrollBy(0, 200)')
                        current_time = time.time()
                        if int(current_time - last_time) > time_distance2:
                            self.driver.refresh()
                            time_distance2 *= 2
                            time.sleep(5)
                            last_time = time.time()
                        elif int(current_time - sentinel_time) > time_distance1:
                            self.driver.execute_script('window.scrollBy(0, -500)')
                            time.sleep(1)
                            sentinel_time = time.time() 
                else:
                    if comments['finish'] is None:
                        comments['finish'] = bottom_elem.text

        
    def new_tab(self, card_feed: WebElement, feed: dict):
        try:
            new_link_elem = card_feed.find_element(By.CLASS_NAME, 'from')
            link_elem = new_link_elem.find_element(By.TAG_NAME, "a")
        except NoSuchElementException as e:
            self.log.warning("[-] card [%s](%s) not has from: %s" % (feed['mid'], self.driver.current_url, str(e)))
        else:
            link = link_elem.get_attribute('href')
            index = link.find('?')
            if index > 0:
                link = link[:index]
            
            pre_handle = self.driver.current_window_handle
            link_elem.send_keys(Keys.RETURN)
            time.sleep(2)
            handles = self.driver.window_handles
            for handle in handles:
                if pre_handle != handle:
                    self.driver.switch_to.window(handle)
            try:
                WebDriverWait(self.driver, 30).until(EC.text_to_be_present_in_element_attribute(
                    (By.XPATH, f'//a[starts-with(@class, "head-info_time")]'), 'href', link)
                )
            except TimeoutException:
                self.log.warning("[-] card [%s](%s) new tab [%s] failed" % (feed['mid'], self.driver.current_url, link))
            else:
                self.parse_new_tab(feed)
            finally:
                if pre_handle != self.driver.current_window_handle:
                    self.driver.close()
                    self.driver.switch_to.window(pre_handle)

    def parse_card(self, parent: WebElement):
        mid = parent.get_attribute('mid')
        if mid is None:
            return None
        feed_dict = { 'mid':  mid , 'top': ''}
        try:
            top_elem = parent.find_element(By.CLASS_NAME, 'card-top')
        except NoSuchElementException:
            pass
        else:
            feed_dict['top'] = top_elem.text
        
        try:
            card = parent.find_element(By.CLASS_NAME, 'card')
        except NoSuchElementException:
            return feed_dict
        
        try:
            card_feed = card.find_element(By.CLASS_NAME, 'card-feed')
        except NoSuchElementException:
            self.log.warning("[-] card [%s](%s) not has card-feed" % (feed_dict['mid'], self.driver.current_url))
        else:
            self.parse_avator(card_feed, feed_dict)
            self.parse_info(card_feed, feed_dict)
            self.parse_from(card_feed, feed_dict)
            self.new_tab(card_feed, feed_dict)
        
        # try:
        #     act = card.find_element(By.CLASS_NAME, "card-act")
        # except NoSuchElementException:
        #     self.log.warning("[-] card [%s](%s) not has card-act" % (feed_dict['mid'], self.driver.current_url))
        # else:
        #     pass

        return feed_dict
    
    @staticmethod
    def strtime(wb_time: str):
        return datetime.strptime('20' + wb_time, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")

    def get_feed_items(self):
        try:
            feed_items = self.driver.find_elements(By.XPATH, '//div[@action-type="feed_list_item"]')
        except Exception as e:
            self.log.error("[-] get_feed_items error: %s")
            return None
        else:
            feed_lists = []
            
            for feed_item in feed_items:
                if feed := self.parse_card(feed_item):
                    if 'comments' not in feed:
                        break
                    users = [(feed['uid'], feed['nick_name'], feed['avator'])]
                    for comment in feed['comments']['comms']:
                        users.append((comment[0], comment[1], comment[2]))
                    self.db.insert_users(users)
                    self.db.insert_messages([(
                        feed['mid'], feed['uid'], feed['top'], feed['from'], self.strtime(feed['time']), feed['content']
                    )])
                    self.db.insert_comments([
                        (feed['mid'], comment[0], self.strtime(comment[3]), comment[4]) for comment in feed['comments']['comms']
                    ])
                    feed_lists.append(feed)
            
            return feed_lists
    
    def next_page(self, question):
        try:
            next_page_elem = self.driver.find_element(By.CLASS_NAME, "next")
        except NoSuchElementException:
            return False
        else:
            next_page_elem.send_keys(Keys.RETURN)
            is_find = False
            for word in question.split(' '):
                try:
                    WebDriverWait(self.driver, 15).until(EC.text_to_be_present_in_element(
                        (By.XPATH, '//p[@node-type="feed_list_content"]'), word)
                    )
                except TimeoutException:
                    continue
                else:
                    is_find = True
                    break
            return is_find

    def crawling(self, question):
        all_feeds = []
        while True:
            feeds = self.get_feed_items()
            all_feeds.append(feeds)
            try:
                if not self.next_page(question):
                    break
            except Exception:
                break

        for feed in all_feeds:
            print(feed)

    def search(self, question: str):
        url = self.search_url + question
        self.driver.get(url)
        
        is_find = False
        for word in question.split(' '):
            try:
                WebDriverWait(self.driver, 10).until(EC.text_to_be_present_in_element(
                    (By.XPATH, '//p[@node-type="feed_list_content"]'), word)
                )
            except TimeoutException:
                continue
            else:
                is_find = True
                break
        if not is_find:
            self.log.error("[-] search %s failed" % url)
            return False

        self.log.info("[.] start crawling ...")
        self.crawling(question)


if __name__ == '__main__':
    driver_path = "chromedriver.exe"
    chrome_port = 9222
    question = "乌克兰"
    
    spider = WeiboSpider(driver_path, comments_path=question.replace(' ', '_') + '.db', debug_port=chrome_port)
    spider.search(question)
