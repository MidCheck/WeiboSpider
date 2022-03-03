from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

import re, time, logging

class WeiboSpider:
    base_url = "https://weibo.com/"
    search_url = "https://s.weibo.com/weibo?q="

    def __init__(self, chromedriver_path: str, debug_port: int=9222, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.service = Service(chromedriver_path)
        self.options = webdriver.ChromeOptions()
        self.options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        self.driver = webdriver.Chrome(service=self.service, options=self.options)
    
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
            wbtext_elem = self.driver.find_element(By.XPATH, '//div[starts-with(@class, "detail_wbtext_")]')
        except NoSuchElementException:
            self.log.warning("[-] [%s](%s) not has detail webtext" % (self.driver.current_url, feed['mid']))
        else:
            feed['content'] = wbtext_elem.text
        
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
                WebDriverWait(self.driver, 5).until(EC.text_to_be_present_in_element_attribute(
                    (By.XPATH, f'//a[contains(@class, "head-info_time")]'), 'href', link)
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
        feed_dict = { 'mid':  mid }
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
                    feed_lists.append(feed)
            
            return feed_lists

    def crawling(self):
        feeds = self.get_feed_items()
        for feed in feeds:
            print(feed)

    def search(self, question: str):
        url = self.search_url + question
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 30).until(EC.text_to_be_present_in_element(
                (By.XPATH, '//p[@node-type="feed_list_content"]'), question)
            )
        except TimeoutException:
            self.log.error("[-] get %s timeout" % url)
            return False
        else:
            self.log.info("[.] start crawling ...")
            self.crawling()


if __name__ == '__main__':
    driver_path = "chromedriver.exe"
    chrome_port = 9222
    question = "乌克兰"
    
    spider = WeiboSpider(driver_path, chrome_port)
    spider.search(question)

