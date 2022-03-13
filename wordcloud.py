from wb_data import WbData
import re
import jieba
import wordcloud
import xlwt


def get_text_from_db(user_path: str, wb_path: str):
    db = WbData(user_path, wb_path)
    contents = ' '.join(db.select_contents())
    db.close()
    return contents

def split_contents(contents):
    counts = dict()
    res = ''
    for s in jieba.lcut(contents):
        if re.match("\w+", s) and len(s) > 1:
            if s not in counts:
                counts[s] = 0
            counts[s] += 1
            if res == '':
                res += s
            else:
                res += ' ' +  s 
    return res, counts

def generate(string: str, png: str):
    w = wordcloud.WordCloud(width=1000,
                        height=700,
                        background_color='white',
                        font_path='msyh.ttc',
                        collocations=False)
    w.generate(string)
    w.to_file(png)

def write_to_excel(excel_path: str, sheet_name: str, data: list):
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(sheet_name)
    for i in range(len(data)):
        for j in range(len(data[i])):
            sheet.write(i, j, data[i][j])
    workbook.save(excel_path)

if __name__ == '__main__':
    question = "乌克兰 俄罗斯"
    path = question.replace(' ', '_')
    contents = get_text_from_db("users.sqlite",  path + ".db")
    strings, counts = split_contents(contents)
    generate(strings, path + '.png')

    lists = sorted(counts.items(), key = lambda kv:(kv[1], kv[0]))
    lists.reverse()
    write_to_excel(path + ".xls", "词频", [('单词', '出现次数')] + lists)
