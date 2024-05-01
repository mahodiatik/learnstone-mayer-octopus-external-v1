import scrapy


class ScrapyBookCrawlerItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class Book(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()