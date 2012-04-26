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
buy_click_re = re.compile("^mB.buyFromMarket\(")

class Web(object):
    def __init__(self, config):
        self.num_requests = 0
        self.config = config
        self.cookie = cookielib.MozillaCookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie))
        self.load_cookie()
        
        self.request_cache = {}
    
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
    
    def read_page(self, url, data=None, cache=False):
        url_data = ''
        if data:
            url_data = urllib.urlencode(data)
        
        if cache:
            key = url + "$$" + url_data
            # check cache
            if key in self.request_cache:
                return self.request_cache[key]
        
        self.num_requests = self.num_requests + 1
        time.sleep(1.0)
        if data:
            r = self.opener.open(url, url_data)
        else:
            r = self.opener.open(url)
        
        if cache:
            self.request_cache[key] = r.read()
            return self.request_cache[key]
            
        return r.read()
        
    def get_page_soup(self, url, data=None, cache=False):
        source = self.read_page(url, data, cache)
        return BeautifulSoup(source)
        
class ProductInfo(object):
    def __init__(self, quality, qty, price):
        self.quality = quality
        self.qty = qty
        self.price = price
        self.normalized_price = self.price - ((self.price * 0.01) * self.quality)

def import_create_prod_info(cells):
    return ProductInfo(
        float(cells[3].text),
        float("inf"),
        float(cells[4].text[1:].replace(',', '')))

def b2b_create_prod_info(cells):
    return ProductInfo(
        float(cells[2].text),
        float(cells[3].text),
        float(cells[4].text[1:].replace(',', '')))

class ReStocker(object):
    def __init__(self, web, config):
        self.web = web
        self.config = config
        
    def _get_prod_info(self, store, prod, store_url_key, store_id_key, create_prod_info):
        prods = []
        for page in range(1, 16):
            soup = self.web.get_page_soup(self.config['urls'][store_url_key].format(self.config["store_classes"][store["class"]][store_id_key], page), cache=True)
            anchor = soup.find('a', text=prod["name"])
            if not anchor and len(prods) > 0:
                return sorted(prods, key=lambda p: p.normalized_price)
            if not anchor:
                continue
            row = anchor.findParent('tr')
            while row:
                try:
                    if not row.find('a', text=prod["name"]):
                        return sorted(prods, key=lambda p: p.normalized_price)
                except TypeError:
                    break
                cells = [cell for cell in row]
                prod_info = create_prod_info(cells)
                prods.append(prod_info)
                buy_anchor = row.find('a', {'onclick': buy_click_re})
                prod_id = re.sub(buy_click_re, '', buy_anchor["onclick"])
                prod_info.prod_id = prod_id[0:prod_id.find(',')]
                row = row.nextSibling
        return sorted(prods, key=lambda p: p.normalized_price)
        
    def get_import_prod_info(self, store, prod):
        return self._get_prod_info(store, prod, 'import_store', 'import_id', import_create_prod_info)
        
    def get_b2b_prod_info(self, store, prod):
        return self._get_prod_info(store, prod, 'b2b_store', 'b2b_id', b2b_create_prod_info)
        
    def buy_b2b_prod(self, prod, prod_info):
        buy_amount = min(prod_info.qty, prod["buy"])
        logging.info("buying {0} of {1}Q ${2} {3} from b2b".format(
                buy_amount, 
                prod_info.quality, 
                prod_info.price, 
                prod["name"]))
        self.web.read_page(self.config['urls']['b2b_buy'].format(prod_info.prod_id, buy_amount))
    
    def buy_import_prod(self, prod, prod_info):
        logging.info("buying {0} of {1}Q ${2} {3} from import".format(
                prod["buy"], 
                prod_info.quality, 
                prod_info.price, 
                prod["name"]))
        self.web.read_page(self.config['urls']['import_buy'].format(prod_info.prod_id, prod["buy"]))
        
    def buy_prod(self, store, prod):
        # get b2b prices/qualities
        b2b_prods = self.get_b2b_prod_info(store, prod)
        import_prods = self.get_import_prod_info(store, prod)
        
        # buy the "best" item available
        if len(b2b_prods) > 0 and b2b_prods[0].normalized_price < import_prods[0].normalized_price:
            self.buy_b2b_prod(prod, b2b_prods[0])
        else:
            self.buy_import_prod(prod, import_prods[0])
        
    def get_prod_qty(self, store_soup, prod):
        img = store_soup.find('img', {'title': prod["name"]})
        if not img:
            logging.warning("could not find product {0}".format(prod["name"]))
            return float("inf")
        prod_div = img.findParent('div', {'class': 'prod_choices_item'})
        out = prod_div.find(text='Out of Stock')
        
        if out:
            return 0
        else:
            qty_anchor = prod_div.find('a', {'title': total_qty_re})    
            qty_str = re.sub(total_qty_re, '', qty_anchor['title']).replace(',', '')
            return int(qty_str)
        
    def process_prod(self, store_soup, store, prod):
        qty = self.get_prod_qty(store_soup, prod)
        if qty == 0:
            self.buy_prod(store, prod)
        elif qty <= int(prod["min"]):
            self.buy_prod(store, prod)
        
    def process_store(self, store):
        logging.info("processing {0}: {1}".format(store["company_name"], store["class"]))
        
        # switch to the stores parent company
        data = {
            'new_active_firm': store["company_id"],
        }
        self.web.read_page(self.config['urls']['switch_company'], data)
        
        # re-stock the products
        store_soup = self.web.get_page_soup(self.config['urls']['store_inv'].format(store["store_id"]))
        for prod in store["products"]:
            self.process_prod(store_soup, store, prod)
        
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
    
    logging.info("re-stocking finished, with {0} requests".format(web.num_requests))


if __name__ == "__main__":
    main()
