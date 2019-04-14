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
        self.Index = {}

    #有些特殊字段，是经过复杂逻辑计算出来的，可以放在该虚函数中处理（在子类中重载）
    def DataPreprocess(self):
        pass
    # 计算每一个字段的类型，默认使用TEXT，可以在子类中重载
    def  field_type(self,f):
        return "TEXT"
    # 在FName列上创建索引，Key->Row
    def BuildIndex(self,FName):
        self.Index.clear()
        for row in self._data:
            self.Index[self.GetCol(row,FName)] = row

    # 从other中获取某个值，并填充到self中去
    # if self[matchColSelf] == other[matchColOther] then self[setColOther] = other[getColOther]
    def AutoFill(self,other,matchColSelf,matchColOther,setColSelf,getColOther,DefaultValue = None):
        other.BuildIndex(matchColOther)
        for row in self._data:
            key = self.GetCol(row,matchColSelf)
            oRow = other.Index.get(key)
            value = None
            if oRow != None:  value = other.GetCol(oRow,getColOther)
            if value == None: value = DefaultValue
            if value != None: self.SetCol(row,setColSelf,value)

    # 获得默认的模板文件所在路径，默认情况下，模板文件与脚本放在同一个目录下，并且模板文件名为   子类类名.fsm
    # 如 Smaps.fsm  MacroValue.fsm等
    def GetDefaultTemplate(self):
        f = os.path.realpath(__file__)
        tmp = self.__class__.__name__
        return os.path.join(os.path.dirname(f),tmp+".fsm")
        
    # 读取解析文件    
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
    
    
    # 获得指定行的特定列  
    def GetCol(self,row,col):
        return row[self.__name2idx[col]].strip()
    # 设置指定行的特定列
    def SetCol(self,row,col,value):
        row[self.__name2idx[col]] = value

    # 将整个表填到sqlite数据库中
    def FillDB(self,dbConnect):
        c = dbConnect.cursor()
        # 如果该table已经存在，先将其删除
        cmd = 'DROP TABLE IF EXISTS  {0}'.format(self.__tblName)
        c.execute(cmd)
        dbConnect.commit()

        # 创建个table
        fields = ''
        for field in self.__fsm.header: 
            fields+='{0} {1},'.format(field,self.field_type(field))
        cmd = 'CREATE TABLE {0} ( {1} )'.format(self.__tblName,fields[:-1])#最后多了一个逗号，过滤掉
        c.execute(cmd)
        dbConnect.commit()
        
        count=0

        print(count)
        # 开始填充数据库
        for row in self._data:
            names = ','.join(self.__fsm.header)
            values = ''
            i = 0
            for v in row:
                # 字符串需要打上双引号，其他类型不用打引号
                if self.field_type(self.__fsm.header[i])=='TEXT': values+='"{0}",'.format(v)
                else: values+='{0},'.format(v)
                i+=1
            
            cmd = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(self.__tblName,names,values[:-1])#最后多了一个逗号，过滤掉
            #print(cmd)
            c.execute(cmd)
            count+=1
                
            
        dbConnect.commit()
        
    # 将整个表填写到excel文件中去
    def FillExcel(self,excel):
        table = excel.add_sheet(self.__tblName,cell_overwrite_ok=True)
        idx = 0
        # 填写第一行：数据标题行header
        for i in range(len(self.__fsm.header)):
            table.write(idx,i,self.__fsm.header[i])
        idx+=1
        # 填写后续行：相关数据
        for row in self._data:
            for col in range(len(row)):
                table.write(idx,col,row[col])
            idx+=1


class Smaps(TxtFsm):

    #哪些字段用字符串方式存储，哪些字段用INT存储
    def field_type(self,f):
        return {'Rss':'INT','Pss':'INT','Size':'INT'}.get(f,'TEXT')

    #有些特殊字段，是经过复杂逻辑计算出来的，可以放在该虚函数中处理
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
    
    mv = MacroValue()
    mv.Parse(r"D:\LinuxMnt\mv.txt")

    smaps.AutoFill(mv,"idx","ID10","idxName","MsgName")

    smaps.FillExcel(excel)
    smaps.FillDB(dbConnect)
    
    mv.FillExcel(excel)
    mv.FillDB(dbConnect)
    
    
    excel.save(excelFile)  # 保存文件
    dbConnect.close()
else:
    print('src not exist!',src)
