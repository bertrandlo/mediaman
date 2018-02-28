# -*- coding: utf-8 -*-
import re


def keyword_extract(strOldName):
    '''
    :param strOldName: 
    :return: (media_id: 番號(string), strNewName: 包含其他修飾文字的媒體名稱(string), m: rex match object) 
    '''

    ext_words = ('HD', 'FHD', 'SD', '1080P')
    exclude_words = ('\[Thz.la\]', 'javcn\.net')        # 需要寫成 regular pattern 格式
    newFileName = strOldName

    for item in exclude_words:                          # 移除 exclude_words
        newFileName = re.sub(item, '', newFileName)

    newFileName = re.sub(r'\[.*?\]', '_', newFileName)  # 移除方括號部份 換成 _

    print('newFileName=', newFileName)

    m = re.compile(r'[0-9a-zA-Z]+[_\-][0-9a-zA-Z]+[_\-]*[0-9a-zA-Z]*').search(newFileName)
    if m:
        media_id = m.group(0).upper()
        strNewName = m.group(0).upper()

        if m.start() > 0:  # 開頭有其他文字
            strNewName = media_id + '_' + strOldName[0:m.start()]

        if m.end() < len(strOldName):  # 結尾或開頭有其他文字
            strNewName = media_id + '_' + re.sub(m.group(0), '', strOldName)
            # strNewName = media_id + '_' + strOldName[m.end():len(strOldName)]

        #print('strNewName=', strNewName)

    else:   # 可能使用了沒有底線或dash的表示方式 改採保守處理  假設為 alpha-num
        m = re.compile(r'[a-zA-Z]+[0-9a-zA-Z]+').search(strOldName)
        if m:
            media_id = m.group(0).upper()
            strNewName = media_id
        else:
            media_id = strOldName
            strNewName = strOldName

    return media_id, strNewName, m


def GetHumanReadable(size, precision=1):
    suffixes=['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s" % (precision, size, suffixes[suffixIndex])


