import re
import sys
import json
import time
import random
import urllib
import urllib2
import logging
import cookielib
from bs4 import BeautifulSoup

CONFIG = 'economies_of_scale.config'

total_qty_re = re.compile("^Total Quantity: ")
import_href_re = re.compile("^/eos/market-import-cat\.php\?cat=")
buy_click_re = re.compile("^mB.buyFromMarket\(")

class Web(object):
    def __init__(self, config):
        self.config = config
        self.cookie = cookielib.MozillaCookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie))
        self.load_cookie()
    
    def load_cookie(self):
        try:
            self.cookie.load('cookie.txt')
            if self.authenticate():
                self.cookie.save(filename='cookie.txt')
            else:
                self.cookie.clear()
                raise

        except:
            if self.authenticate():
                self.cookie.save(filename='cookie.txt')
            else:
                logging.error('Login failed, exiting.')
                sys.exit(1)
    
    def authenticate(self):
        data = (
            ('username', self.config['username']),
            ('password', self.config['password']),
            ('nocache', random.random())
        )
        ret = self.read_page(self.config['urls']['login'], data)
        if ret == 'OK':
            # This is needed to validate login
            d = self.read_page(self.config['urls']['home'])
            logging.info("successfully logged in")
            return True
        else:
            return False
    
    def read_page(self, url, data=None):
        time.sleep(1.0)
        if data:
            r = self.opener.open(url, urllib.urlencode(data))
        else:
            r = self.opener.open(url)
        return r.read()
        
    def get_page_soup(self, url, data=None):
        source = self.read_page(url, data)
        return BeautifulSoup(source)

class ReStocker(object):
    def __init__(self, web, config):
        self.web = web
        self.config = config
        
    def buy_prod(self, prod_div, prod):
        # get category id
        import_anchor = prod_div.find('a', {'href': import_href_re})
        cat_id = re.sub(import_href_re, '', import_anchor["href"])
        
        # loop through cetegory pages until find correct page
        for page_num in range(1, 16):
            soup = self.web.get_page_soup(self.config['urls']['import_cat'].format(cat_id, page_num))
            img = soup.find('img', {'title': prod["name"]})
            if img:
                # get the product id
                prod_row = img.findParent('tr')
                buy_anchor = prod_row.find('a', {'onclick': buy_click_re})
                prod_id = re.sub(buy_click_re, '', buy_anchor["onclick"])
                index = prod_id.find(',')
                prod_id = prod_id[0:index]
                # buy the product
                self.web.read_page(self.config['urls']['buy_page'].format(prod_id, prod["buy"]))
                return True
        
        logging.warning("product {0} not found".format(prod["name"]))
        return False
        
    def process_prod(self, store_soup, prod):
        img = store_soup.find('img', {'title': prod["name"]})
        if not img:
            print store_soup.prettify()
            logging.warning("could not find product {0}".format(prod["name"]))
            return
        prod_div = img.findParent('div', {'class': 'prod_choices_item'})
        out = prod_div.find(text='Out of Stock')
        
        if out:
            logging.info("    out of {0}, re-stocking {1}".format(prod["name"], prod["buy"]))
            self.buy_prod(prod_div, prod)
        else:
            qty_anchor = prod_div.find('a', {'title': total_qty_re})    
            qty_str = re.sub(total_qty_re, '', qty_anchor['title']).replace(',', '')
            
            if int(qty_str) < int(prod["min"]):
                logging.info("    insufficient {0}, re-stocking {1}".format(prod["name"], prod["buy"]))
                self.buy_prod(prod_div, prod)
            #else:
            #    logging.info("    sufficient {0}".format(prod["name"]))
        
    def process_store(self, store):
        logging.info("processing {0}: {1}".format(store["company_name"], store["name"]))
        
        # switch to the stores parent company
        data = {
            'new_active_firm': store["company_id"],
        }
        self.web.read_page(self.config['urls']['switch_company'], data)
        
        # re-stock the products
        store_soup = self.web.get_page_soup(self.config['urls']['store_inv'].format(store["store_id"]))
        for prod in store["products"]:
            self.process_prod(store_soup, prod)
        
        # then hit the lazy x2 button
        self.web.read_page(self.config['urls']['store_lazyx2'].format(store["store_id"]))
    
    def go(self):
        for store in self.config["stores"]:
            self.process_store(store)

def load_config(path=CONFIG):
    # Load main config file
    try:
        return json.load(open(path))
    except ValueError, e:
        logging.error("Error parsing configuration {0}: {1}".format(CONFIG, e))
        sys.exit(1)

def main():
    # set-up logging
    logging.basicConfig(
        filename='economies_of_scale.log', 
        filemode='a', level=logging.DEBUG, 
        format='[%(levelname)s:%(asctime)s]%(message)s',
        datefmt='%m/%d/%Y %H:%M:%S'
        )
    
    logging.info("starting re-stocking")
    
    config = load_config()
    web = Web(config)
    
    restocker = ReStocker(web, config)
    restocker.go()
    
    logging.info("re-stocking finished")


if __name__ == "__main__":
    main()