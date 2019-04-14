import textfsm
import os
from optparse import OptionParser
import sqlite3
import xlwt
class TxtFsm:
    def __init__(self):
        self._data = None
        self.__name2idx = {}
        self.__fsm = None
        self.__tblName = None
    def DataPreprocess(self):
        pass
    def  field_type(self,f):
        return "TEXT"
    
    def GetDefaultTemplate(self):
        f = os.path.realpath(__file__)
        tmp = self.__class__.__name__
        return os.path.join(os.path.dirname(f),tmp+".fsm")
        
        
    def Parse(self,src,tblName = None,tmp = None):
        if not tmp:tmp = self.GetDefaultTemplate()
        if not tblName:tblName = self.__class__.__name__
        
        self.__tblName = tblName
        txt=''
        with open(src,'r+') as f: txt = f.read()
        with open(tmp,'r+') as f: self.__fsm = textfsm.TextFSM(f)
        self._data = self.__fsm.ParseText(txt)
        for i in range(len(self.__fsm.header)):
            self.__name2idx[self.__fsm.header[i]]=i
        self.DataPreprocess()
    
    
        
    def GetCol(self,row,col):
        return row[self.__name2idx[col]].strip()
    def SetCol(self,row,col,value):
        row[self.__name2idx[col]] = value

    def FillDB(self,dbConnect):
        c = dbConnect.cursor()
        # Create Table
        fields = ''
        for field in self.__fsm.header: 
            fields+='{0} {1},'.format(field,self.field_type(field))
        cmd = 'DROP TABLE IF EXISTS  {0}'.format(self.__tblName)
        c.execute(cmd)
        dbConnect.commit()
        cmd = 'CREATE TABLE {0} ( {1} )'.format(self.__tblName,fields[:-1])
        c.execute(cmd)
        dbConnect.commit()
        
        count=0

        print(count)
        # Fill DB
        for row in self._data:
            names = ','.join(self.__fsm.header)
            values = ''
            i = 0
            for v in row:
                if self.field_type(self.__fsm.header[i])=='TEXT': values+='"{0}",'.format(v)
                else: values+='{0},'.format(v)
                i+=1
            
            cmd = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(self.__tblName,names,values[:-1])
            #print(cmd)
            c.execute(cmd)
            count+=1
                
            
        dbConnect.commit()

    def FillExcel(self,excel):
        table = excel.add_sheet(self.__tblName,cell_overwrite_ok=True)
        idx = 0
        #header
        for i in range(len(self.__fsm.header)):
            table.write(idx,i,self.__fsm.header[i])
        idx+=1
        #data
        for row in self._data:
            for col in range(len(row)):
                table.write(idx,col,row[col])
            idx+=1


class Smaps(TxtFsm):

    #这个地方硬编码
    def field_type(self,f):
        return {'Rss':'INT','Pss':'INT','Size':'INT'}.get(f,'TEXT')
    def DataPreprocess(self):
        
        preRow = None
        idx = 0
        for row in self._data:
            idx+=1
            begin = self.GetCol(row,"Begin")
            end = self.GetCol(row,"End") 
            perms = self.GetCol(row,"Perms")
            path = self.GetCol(row,"PathName")
            type='?'
            #print('path =',path,'isheap=','[heap' in path)
            if '[stack' in path:        #stack
                type = path
            elif '[heap' in path:    # heap
                type = path
            elif 'r-xp' in perms:         
                if len(path)>0: type = 'textcode.file' #可执行
            elif 'rw-p' in perms: #可读写
                if len(path)>0: type = 'data(plt..).file' #全局变量 or plt段等
                elif len(path)==0 and preRow and begin == self.GetCol(preRow,'End') and len(self.GetCol(preRow,'PathName'))>0: type = 'bss.nofile'
                else: type = 'malloc|ub'
            elif 'r--p' in perms:
                if len(path)>0: type = 'readonlydata.file'
                else: type = 'readonlydata.nofile'
            elif '---p' in perms:
                type = 'page.protected'
            self.SetCol(row,'idx',str(idx))
            self.SetCol(row,'type',type)
            preRow = row  
#

class MacroValue(TxtFsm):
    def field_type(self,f):
        return {'ID10':'INT'}.get(f,'TEXT')
#
#

src = r"D:\LinuxMnt\2721.smaps.txt"
if src and os.path.isfile(src):
    dbFile = src+".db"
    excelFile = src+".xls"
    if os.path.isfile(excelFile):os.remove(excelFile)

    dbConnect = sqlite3.connect(dbFile)
    excel = xlwt.Workbook()
    
    smaps = Smaps()
    smaps.Parse(src)
    smaps.FillExcel(excel)
    smaps.FillDB(dbConnect)
    
    mv = MacroValue()
    mv.Parse(r"D:\LinuxMnt\mv.txt")
    mv.FillExcel(excel)
    mv.FillDB(dbConnect)
    
    excel.save(excelFile)  # 保存文件
    dbConnect.close()
else:
    print('src not exist!',src)