#"""
#This demo demonstrates how to draw a dynamic mpl (matplotlib) 
#plot in a wxPython application.

#It allows "live" plotting as well as manual zooming to specific
#regions.

#Both X and Y axes allow "auto" or "manual" settings. For Y, auto
#mode sets the scaling of the graph to see all the data points.
#For X, auto mode makes the graph "follow" the data. Set it X min
#to manual 0 to always see the whole data from the beginning.

#Note: press Enter in the 'manual' text box to make a new value 
#affect the plot.

#Eli Bendersky (eliben@gmail.com)
#License: this code is in the public domain
#Last modified: 31.07.2008
#xdmiodz 6.05.2011  modified for own purposes
#"""
import os
import pprint
import random
import sys
import wx
import ConfigParser
import atexit, shutil, datetime
from guidata.dataset.datatypes import DataSet, BeginGroup, EndGroup
from guidata.dataset.dataitems import (FloatItem, IntItem, BoolItem, ChoiceItem,
				       MultipleChoiceItem, ImageChoiceItem, FilesOpenItem,
				       StringItem, TextItem, ColorItem, FileSaveItem,
				       FileOpenItem, DirectoryItem, FloatArrayItem,
				       DateItem, DateTimeItem, DataItem)

from guidata.dataset.qtwidgets import DataSetEditLayout, DataSetShowLayout, LineEditWidget
from guidata.dataset.qtitemwidgets import LineEditWidget, DataSetWidget
import guidata

# The recommended way to use wx with mpl is with the WXAgg
# backend. 
#
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import \
	FigureCanvasWxAgg as FigCanvas, \
	NavigationToolbar2WxAgg as NavigationToolbar
import numpy as np
import pylab
import subprocess
import tempfile

class EvalStringItem(StringItem):
	def check_value(self, value):
		try:
			val = eval(str(value))
		except:
			return False
		return (str(int(float(val)))).isdigit() 

class TestParameters(DataSet):
	_bg = BeginGroup("R/W Commands")
	readcmd = FileOpenItem("Reading command", "exe", "")
	writecmd = FileOpenItem("Writing command", "exe", "")
	_eg = EndGroup("R/W Commands")
	
	_bg = BeginGroup("Channels")
	ch1n = IntItem("Channel #1", default=3, min=1, max=4)
	ach1n = EvalStringItem("K1", default="1").set_pos(col=1)
	ch2n = IntItem("Channel #2", default=4, min=1, max=4)
	ach2n = EvalStringItem("K2", default="1").set_pos(col=1)
	_eg = EndGroup("Channels")

	_bg = BeginGroup("Pulse")
	period = FloatItem("Period", min=0.5, default = 1.0, help="Time between two sequential clock pulse")
	duration = FloatItem("Duration", min=0.5, max = period, default = 0.7, help="Duaration of the clock pulse")
	syncch =  IntItem("#Sync channel", default=1, min=1, max=2, help="The sync DAC channel")
	_eg = EndGroup("Pulse")

class DataWrite(object):
	""" Class to write data to usb3000
	"""
	def writedata(self, writecmd, channel, duration):
		normcmd = os.path.normpath(writecmd)
		args = [normcmd, str(duration), str(channel)]
		print 'write to DAC'
		r = subprocess.call(args)

class DataGen(object):
	""" Class to read data from usb300
		and save it to the internal varibale or a file
	"""
	def __init__(self):
		self.ch1 = np.array([], dtype=np.int32)
		self.ch2 = np.array([], dtype=np.int32)
		self.time = np.array([])
		
	def update(self, readcmd, ch1, ch2, pulse_period, Ach1, Ach2):
		fromfile =  tempfile.mktemp()
		normcmd = os.path.normpath(readcmd)
		args = [normcmd, fromfile]
		print 'read from ADC'
		r = subprocess.call(args)
		t=np.fromfile(fromfile, dtype=pylab.int16)
		l = np.size(t)
		#l = 0
		#ch1nval = 1
		#ch2nval = 2
		ch1nval = Ach1*np.mean(np.array([t[4*i+ch1] for i in xrange(int(l/4))]))
		ch2nval = Ach2*np.mean(np.array([t[4*i+ch2] for i in xrange(int(l/4))]))
		#ch1nval = (837/664.5)*5*2000*np.mean(np.array([t[4*i+ch1] for i in xrange(int(l/4))]))/8192/1.024
		#ch2nval = (837/799.8)*5*330*np.mean(np.array([t[4*i+ch2] for i in xrange(int(l/4))]))/8192
		print 'ch' + str(int(ch1+1)) + ' = ' + str(int(ch1nval)) + ' V/m'
		print 'ch' + str(int(ch2+1)) + ' = ' + str(int(ch2nval)) + ' V/m'
		self.ch1 = np.append(self.ch1, [int(ch1nval)])
		self.ch2 = np.append(self.ch2, [int(ch2nval)])
		l = np.size(self.time)
		if l==0:
			lastt = 0
		else:
			lastt=self.time[l-1]
		
		self.time = np.append(self.time, [lastt + pulse_period])
		os.remove(fromfile)
		return [self.ch1, self.ch2, self.time]
		 
		
	def savedata(self, ch1f, ch2f, tf):
		np.save(ch1f, self.ch1)
		np.save(ch2f, self.ch2)
		np.save(tf, self.tf)
	
	def get_readcmd(self):
		return self.readcmd
		
	def set_readcmd(self,readcmd):
		self.readcmd = readcmd
	

class BoundTextBox(wx.Panel):
	def __init__(self, parent, ID, label, desc1, desc2, initval1, initval2):
		wx.Panel.__init__(self, parent, ID)
		self.value1 = initval1
		self.value2 = initval2
		self.box1 = wx.BoxSizer(wx.HORIZONTAL)
		self.box2 = wx.BoxSizer(wx.HORIZONTAL)
		box = wx.StaticBox(self, -1, label)
		sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		
		self.manual_text1 = wx.TextCtrl(self, -1, 
						size=(-1,-1),
						value=str(initval1),
						style=wx.TE_PROCESS_ENTER)
		self.manual_text2 = wx.TextCtrl(self, -1, 
						size=(-1,-1),
						value=str(initval2),
						style=wx.TE_PROCESS_ENTER)
		
		self.desc_text1 = wx.StaticText(self, -1,  
						desc1, (0,0), 
						(-1,-1), 0, 
						"")
		
		self.desc_text2 = wx.StaticText(self, -1,  
						desc2, (0,0), 
						(-1,-1), 0, 
						"")
		self.box1.Add(self.desc_text1, 1, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER)
		self.box1.Add(self.manual_text1, 1, flag=wx.ALIGN_RIGHT| wx.ALIGN_CENTER)

		self.box2.Add(self.desc_text2, 1,flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER)
		self.box2.Add(self.manual_text2, 1,  flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER)

		#self.Bind(wx.EVT_UPDATE_UI, self.on_update_manual_text, self.manual_text)
		self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter, self.manual_text1)
		self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter, self.manual_text2)

		sizer.Add(self.box1, 0, wx.ALL, 10)
		sizer.Add(self.box2, 0, wx.ALL, 10)

		self.SetSizer(sizer)
		sizer.Fit(self)

	#def on_update_manual_text(self, event):
	 #   self.manual_text.Enable(self.manual_text.GetValue())
	
	def on_text_enter(self, event):
		self.value1 = self.manual_text1.GetValue()
		self.value2 = self.manual_text2.GetValue()

	def manual_value(self):
		return [self.manual_text1.GetValue(), self.manual_text2.GetValue()]
		
class BoundFileBox(BoundTextBox):
	def __init__(self, parent, ID, label, desc1, desc2, initval1, initval2):
		BoundTextBox.__init__(self, parent, ID, label, desc1, desc2, initval1, initval2)
		self.manual_text1.Bind(wx.EVT_LEFT_DCLICK, self.on_dclick1)
		self.manual_text2.Bind(wx.EVT_LEFT_DCLICK, self.on_dclick2)
	
	def on_text_dclick(self):
		file_choices = "EXE (*.exe)|*.exe"
		
		dlg = wx.FileDialog(self, 
				    message="Select the program...",
				    defaultDir=os.getcwd(),
				    defaultFile="",
				    wildcard=file_choices,
				    style=wx.OPEN)
		
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			return path
			
	def on_dclick1(self, event):
		path = self.on_text_dclick()
		self.manual_text1.SetValue(str(path))
		
	def on_dclick2(self, event):
		path = self.on_text_dclick()
		self.manual_text2.SetValue(str(path))


class BoundControlBox(wx.Panel):
	""" A static box with a couple of radio buttons and a text
		box. Allows to switch between an automatic mode and a 
		manual mode with an associated value.
	"""
	def __init__(self, parent, ID, label, initval):
		wx.Panel.__init__(self, parent, ID)
		
		self.value = initval
		
		box = wx.StaticBox(self, -1, label)
		sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		
		self.radio_auto = wx.RadioButton(self, -1, 
						 label="Auto", style=wx.RB_GROUP)
		self.radio_manual = wx.RadioButton(self, -1,
						   label="Manual")
		self.manual_text = wx.TextCtrl(self, -1, 
					       size=(35,-1),
					       value=str(initval),
					       style=wx.TE_PROCESS_ENTER)
		
		self.Bind(wx.EVT_UPDATE_UI, self.on_update_manual_text, self.manual_text)
		self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter, self.manual_text)
		
		manual_box = wx.BoxSizer(wx.HORIZONTAL)
		manual_box.Add(self.radio_manual, flag=wx.ALIGN_CENTER_VERTICAL)
		manual_box.Add(self.manual_text, flag=wx.ALIGN_CENTER_VERTICAL)
		
		sizer.Add(self.radio_auto, 0, wx.ALL, 10)
		sizer.Add(manual_box, 0, wx.ALL, 10)
		
		self.SetSizer(sizer)
		sizer.Fit(self)
	
	def on_update_manual_text(self, event):
		self.manual_text.Enable(self.radio_manual.GetValue())
	
	def on_text_enter(self, event):
		self.value = self.manual_text.GetValue()
	
	def is_auto(self):
		return self.radio_auto.GetValue()
		
	def manual_value(self):
		return self.value


class GraphFrame(wx.Frame):
	""" The main frame of the application
	"""
	title = 'Project: The Helicopter'
	
	def __init__(self):
		wx.Frame.__init__(self, None, -1, self.title)
		self.config = ConfigParser.RawConfigParser()
		default_config = os.getcwd() + '/helicopter.ini'
		self.e = TestParameters()
		if os.path.isfile(default_config):
			self.config.read(default_config)
			self.copy_dataset_from_configparser()
		else:
			self.config=self.make_default_config()
			self.copy_dataset_from_configparser()
			with open(default_config, 'wb') as configfile:
				self.config.write(configfile)
		self.dataread = DataGen()
		self.datawrite = DataWrite()
		self.data = np.array([0],dtype=np.int32)
		self.data2 = np.array([0], dtype=np.int32)
		self.time = np.array([0])
		self.paused = False
		
		self.create_menu()
		self.create_status_bar()
		self.create_main_panel()
		
		self.redraw_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.on_redraw_timer, self.redraw_timer)	
		self.redraw_timer.Start(int(float(self.e.period)*1000))
	
	def on_update_config(self):
		self.config.set('cmds', 'readcmd', self.e.readcmd)
		self.config.set('cmds', 'writecmd', self.e.writecmd)
		
		self.config.set('pulse', 'duration', self.e.duration)
		self.config.set('pulse', 'period', self.e.period)
		self.config.set('pulse', 'syncch', self.e.syncch)
		
		self.config.set('channels', 'ch1', self.e.ch1n)
		self.config.set('channels', 'ch2', self.e.ch2n)
		self.config.set('channels', 'ach1', self.e.ach1n)
		self.config.set('channels', 'ach2', self.e.ach2n)
		
	def make_default_config(self):
		config = ConfigParser.RawConfigParser()
		
		config.add_section('pulse')
		config.set('pulse', 'period', '10.0')
		config.set('pulse', 'duration', '0.7')
		config.set('pulse', 'syncch', '1')
		
		config.add_section('cmds')
		config.set('cmds', 'readcmd', 'read_usb3000.exe')
		config.set('cmds', 'writecmd', 'write_usb3000.exe')

		config.add_section('channels')
		config.set('channels', 'ch1', '3')
		config.set('channels', 'ch2', '4')
		config.set('channels', 'ach1', '(1525/1572.8)*(837/664.5)*5*2000/8192/1.024')
		config.set('channels', 'ach2', '(837/799.8)*5*330/8192')
		
		config.add_section('autosave')
		config.set('autosave', 'on', 'true')
		config.set('autosave', 'timer', '30')
		return config
		
	def copy_dataset_from_configparser(self):
		self.e.readcmd = self.config.get('cmds', 'readcmd')
		self.e.writecmd = self.config.get('cmds', 'writecmd')
		
		self.e.duration = self.config.get('pulse', 'duration')
		self.e.period = self.config.get('pulse', 'period')
		self.e.syncch = self.config.get('pulse', 'syncch')
		
		self.e.ch1n = self.config.get('channels', 'ch1')
		self.e.ch2n = self.config.get('channels', 'ch2')
		self.e.ach1n = self.config.get('channels', 'ach1')
		self.e.ach2n = self.config.get('channels', 'ach2')

	def create_menu(self):
		self.menubar = wx.MenuBar()
		menu_file = wx.Menu()
		m_expt = menu_file.Append(-1, "&Save plot\tCtrl-P", "Save plot to file")
		self.Bind(wx.EVT_MENU, self.on_save_plot, m_expt)
		m_savedata = menu_file.Append(-1, "&Save data\tCtrl-D", "Save channels to file")
		self.Bind(wx.EVT_MENU, self.on_save_data, m_savedata)
		m_savedata = menu_file.Append(-1, "&Save configuration\tCtrl-C", "Save configuarution to file")
		self.Bind(wx.EVT_MENU, self.on_save_config, m_savedata)
		menu_file.AppendSeparator()
		m_exit = menu_file.Append(-1, "E&xit\tCtrl-X", "Exit")
		self.Bind(wx.EVT_MENU, self.on_exit, m_exit)
		self.menubar.Append(menu_file, "&File")
		self.SetMenuBar(self.menubar)

	def create_main_panel(self):
		self.panel = wx.Panel(self)
		self.init_plot()
		self.canvas = FigCanvas(self.panel, -1, self.fig)
		self.xmin_control = BoundControlBox(self.panel, -1, "X1 min", 0)
		self.xmax_control = BoundControlBox(self.panel, -1, "X1 max", 60)
		self.ymin_control = BoundControlBox(self.panel, -1, "Y1 min", 0)
		self.ymax_control = BoundControlBox(self.panel, -1, "Y1 max", 100)

		self.xmin_control2 = BoundControlBox(self.panel, -1, "X2 min", 0)
		self.xmax_control2 = BoundControlBox(self.panel, -1, "X2 max", 60)
		self.ymin_control2 = BoundControlBox(self.panel, -1, "Y2 min", 0)
		self.ymax_control2 = BoundControlBox(self.panel, -1, "Y2 max", 100)
		
		readcmd = self.config.get('cmds', 'readcmd')
		writecmd = self.config.get('cmds', 'writecmd')
		period = self.config.getfloat('pulse', 'period')
		duration = self.config.getfloat('pulse', 'duration')
		
		self.pulse_control = BoundTextBox(self.panel, -1, "Pulse", "Period, sec", 
						  "Duration, sec", period, duration)
		self.cmd_control = BoundFileBox(self.panel, -1, "Cmds", "Read cmd", 
						"Write cmd", readcmd, writecmd)
										  
		[RC, WC] = self.cmd_control.manual_value()
		self.dataread.set_readcmd(RC)
		self.pause_button = wx.Button(self.panel, -1, "Pause")
		self.Bind(wx.EVT_BUTTON, self.on_pause_button, self.pause_button)
		self.Bind(wx.EVT_UPDATE_UI, self.on_update_pause_button, self.pause_button)
		
		self.config_button = wx.Button(self.panel, -1, "Configuration")
		self.Bind(wx.EVT_BUTTON, self.on_config_button, self.config_button)

		self.cb_grid = wx.CheckBox(self.panel, -1, 
			"Show Grid",
			style=wx.ALIGN_RIGHT)
		self.Bind(wx.EVT_CHECKBOX, self.on_cb_grid, self.cb_grid)
		self.cb_grid.SetValue(True)
		
		self.cb_xlab = wx.CheckBox(self.panel, -1, 
			"Show X labels",
			style=wx.ALIGN_RIGHT)
		self.Bind(wx.EVT_CHECKBOX, self.on_cb_xlab, self.cb_xlab)		
		self.cb_xlab.SetValue(True)
		
		self.hbox1 = wx.BoxSizer(wx.HORIZONTAL)
		self.hbox1.Add(self.pause_button, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
		self.hbox1.AddSpacer(20)
		self.hbox1.Add(self.config_button, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
		self.hbox1.AddSpacer(20)
		self.hbox1.Add(self.cb_grid, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
		self.hbox1.AddSpacer(10)
		self.hbox1.Add(self.cb_xlab, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
		
		self.hbox2 = wx.BoxSizer(wx.HORIZONTAL)
		self.hbox2.Add(self.xmin_control, border=5, flag=wx.ALL)
		self.hbox2.Add(self.xmax_control, border=5, flag=wx.ALL)
		self.hbox2.AddSpacer(2)
		self.hbox2.Add(self.ymin_control, border=5, flag=wx.ALL)
		self.hbox2.Add(self.ymax_control, border=5, flag=wx.ALL)

		self.hbox3 = wx.BoxSizer(wx.HORIZONTAL)
		self.hbox3.Add(self.xmin_control2, border=5, flag=wx.ALL)
		self.hbox3.Add(self.xmax_control2, border=5, flag=wx.ALL)
		self.hbox3.AddSpacer(2)
		self.hbox3.Add(self.ymin_control2, border=5, flag=wx.ALL)
		self.hbox3.Add(self.ymax_control2, border=5, flag=wx.ALL)

		self.hbox4 = wx.BoxSizer(wx.HORIZONTAL)
		self.hbox4.Add(self.pulse_control, border=5, flag=wx.ALL)
		self.hbox4.Add(self.cmd_control, border=5, flag=wx.ALL)
		
		self.cbox = wx.BoxSizer(wx.VERTICAL)
		self.cbox.Add(self.hbox1, 0, flag=wx.ALIGN_LEFT | wx.TOP)
		self.cbox.Add(self.hbox2, 0, flag=wx.ALIGN_LEFT | wx.TOP)
		self.cbox.Add(self.hbox3, 0, flag=wx.ALIGN_LEFT | wx.TOP)
		self.cbox.Add(self.hbox4, 0, flag=wx.ALIGN_LEFT | wx.TOP)
		
		self.vbox = wx.BoxSizer(wx.HORIZONTAL)
		self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)		
		self.vbox.Add(self.cbox, 1, flag=wx.ALIGN_LEFT | wx.TOP)	 	
		
		self.panel.SetSizer(self.vbox)
		self.vbox.Fit(self)

	def on_config_button(self, event):
		self.paused=True
		self.on_update_pause_button(event)
		self.e.edit()
		self.paused=False
		self.on_update_pause_button(event)
		self.on_update_config()
	
	def create_status_bar(self):
		self.statusbar = self.CreateStatusBar()

	def init_plot(self):
		self.dpi = 100
		self.fig = Figure((3.0, 3.0), dpi=self.dpi)

		self.axes = self.fig.add_subplot(211)
		self.axes.set_axis_bgcolor('black')
		self.axes.set_title('Channel 1', size=10)
		self.axes2 = self.fig.add_subplot(212)
		self.axes2.set_axis_bgcolor('black')
		self.axes2.set_title('Channel 2', size=10)
		self.axes2.set_xlabel('Time, secs', size=10)
		#self.axes.set_xticks([])

		pylab.setp(self.axes.get_xticklabels(), fontsize=8)
		pylab.setp(self.axes.get_yticklabels(), fontsize=8)
		
		pylab.setp(self.axes2.get_xticklabels(), fontsize=8)
		pylab.setp(self.axes2.get_yticklabels(), fontsize=8)
		
		pylab.setp(self.axes.get_xticklabels(), visible=0)

		# plot the data as a line series, and save the reference 
		# to the plotted line series
		#
		self.plot_data = self.axes.plot(
			self.data, 
			linewidth=1,
			color=(1, 1, 0),
			)[0]

		self.plot_data2 = self.axes2.plot(
			self.data2, 
			linewidth=1,
			color=(1, 1, 0),
			)[0]

	def draw_plot(self):
		""" Redraws the plot
		"""
		# when xmin is on auto, it "follows" xmax to produce a 
		# sliding window effect. therefore, xmin is assigned after
		# xmax.
		#
		if self.xmax_control.is_auto():
			xmax = len(self.data) if len(self.data) > 50 else 50
		else:
			xmax = int(self.xmax_control.manual_value())
			
		if self.xmin_control.is_auto():			
			xmin = xmax - 50
		else:
			xmin = int(self.xmin_control.manual_value())

		if self.xmax_control2.is_auto():
			xmax2 = len(self.data2) if len(self.data2) > 50 else 50
		else:
			xmax2 = int(self.xmax_control2.manual_value())
			
		if self.xmin_control2.is_auto():			
			xmin2 = xmax2 - 50
		else:
			xmin2 = int(self.xmin_control2.manual_value())

		# for ymin and ymax, find the minimal and maximal values
		# in the data set and add a mininal margin.
		# 
		# note that it's easy to change this scheme to the 
		# minimal/maximal value in the current display, and not
		# the whole data set.
		# 
		if self.ymin_control.is_auto():
			ymin = round(min(self.data), 0) - 1
		else:
			ymin = int(self.ymin_control.manual_value())
		
		if self.ymax_control.is_auto():
			ymax = round(max(self.data), 0) + 1
		else:
			ymax = int(self.ymax_control.manual_value())

		if self.ymin_control2.is_auto():
			ymin2 = round(min(self.data2), 0) - 1
		else:
			ymin2 = int(self.ymin_control2.manual_value())
		
		if self.ymax_control2.is_auto():
			ymax2 = round(max(self.data2), 0) + 1
		else:
			ymax2 = int(self.ymax_control2.manual_value())

		self.axes.set_xbound(lower=xmin, upper=xmax)
		self.axes.set_ybound(lower=ymin, upper=ymax)

		self.axes2.set_xbound(lower=xmin2, upper=xmax2)
		self.axes2.set_ybound(lower=ymin2, upper=ymax2)
		
		# anecdote: axes.grid assumes b=True if any other flag is
		# given even if b is set to False.
		# so just passing the flag into the first statement won't
		# work.
		#
		if self.cb_grid.IsChecked():
			self.axes.grid(True, color='gray')
			self.axes2.grid(True, color='gray')
		else:
			self.axes.grid(False)
			self.axes2.grid(False)

		# Using setp here is convenient, because get_xticklabels
		# returns a list over which one needs to explicitly 
		# iterate, and setp already handles this.
		#  
		pylab.setp(self.axes.get_xticklabels(), visible=0)

		pylab.setp(self.axes2.get_xticklabels(), 
			visible=self.cb_xlab.IsChecked())
		
		self.plot_data.set_xdata(self.time/1000)
		self.plot_data.set_ydata(self.data)
		
		self.plot_data2.set_xdata(self.time/1000)
		self.plot_data2.set_ydata(self.data2)
		
		self.canvas.draw()
  
	def on_pause_button(self, event):
		self.paused = not self.paused
	
	def on_update_pause_button(self, event):
		label = "Resume" if self.paused else "Pause"
		self.pause_button.SetLabel(label)
	
	def on_cb_grid(self, event):
		self.draw_plot()
	
	def on_cb_xlab(self, event):
		self.draw_plot()
	
	def on_save_plot(self, event):
		file_choices = "PNG (*.png)|*.png"
		
		dlg = wx.FileDialog(
			self, 
			message="Save plot as...",
			defaultDir=os.getcwd(),
			defaultFile="plot.png",
			wildcard=file_choices,
			style=wx.SAVE)
		
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			self.canvas.print_figure(path, dpi=self.dpi)
			self.flash_status_message("Plot saved to %s" % path)
	
	def on_save_data(self, event):
		file_choices = "NPZ (*.npz)|*.npz"
		
		dlg = wx.FileDialog(
			self, 
			message="Save data as...",
			defaultDir=os.getcwd(),
			defaultFile="channels.npz",
			wildcard=file_choices,
			style=wx.SAVE)
		
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			np.savez(path, ch1=self.data, ch2=self.data2, time=self.time)
			self.flash_status_message("Data saved to %s" % path)

	def on_save_config(self, event):
		file_choices = "INI (*.ini)|*.ini"
		dlg = wx.FileDialog(self, 
				    message="Save configuration as...",
				    defaultDir=os.getcwd(),
				    defaultFile="helicopter.ini",
				    wildcard=file_choices,
				    style=wx.SAVE)
		
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			with open(path, 'wb') as configfile:
				self.config.write(configfile)
			self.flash_status_message("Config saved to %s" % path)
		
	def on_redraw_timer(self, event):
		# if paused do not add data, but still redraw the plot
		# (to respond to scale modifications, grid change, etc.)
		#

		if not self.paused:
			ch1 = self.config.getint('channels', 'ch1') - 1
			ch2 = self.config.getint('channels', 'ch2') - 1
			Ach1 = eval(self.config.get('channels', 'Ach1'))
			Ach2 = eval(self.config.get('channels', 'Ach2'))
			readcmd = self.config.get('cmds','readcmd')
			writecmd = self.config.get('cmds','writecmd')
			syncch = self.config.getint('pulse', 'syncch')
			duration = self.config.getfloat('pulse', 'duration')*1000
			self.datawrite.writedata(writecmd, syncch, duration)
			[self.data, self.data2, self.time] = self.dataread.update(readcmd, ch1, ch2, self.redraw_timer.GetInterval(), Ach1, Ach2)
		self.draw_plot()
		
		if self.redraw_timer.GetInterval() != int(float(self.e.period)*1000):
			self.redraw_timer.Stop()
			self.redraw_timer.Start(int(float(self.e.period)*1000))
	
	def on_exit(self, event):
		self.Destroy()
	
	def flash_status_message(self, msg, flash_len_ms=1500):
		self.statusbar.SetStatusText(msg)
		self.timeroff = wx.Timer(self)
		self.Bind(
			wx.EVT_TIMER, 
			self.on_flash_status_off, 
			self.timeroff)
		self.timeroff.Start(flash_len_ms, oneShot=True)
	
	def on_flash_status_off(self, event):
		self.statusbar.SetStatusText('')


if __name__ == '__main__':
	_app = guidata.qapplication()
	DataSetEditLayout.register(EvalStringItem, LineEditWidget)
	DataSetShowLayout.register(EvalStringItem, LineEditWidget)
	app = wx.PySimpleApp()
	app.frame = GraphFrame()
	app.frame.Show()
	app.MainLoop()

