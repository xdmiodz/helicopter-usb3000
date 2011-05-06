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


class DataGen(object):
    """ A silly class that generates pseudo-random data for
        display in the plot.
    """
    def __init__(self, init=50):
        self.data = self.init = init
        
    def next(self):
        self._recalc_data()
        return self.data
    
    def _recalc_data(self):
        delta = random.uniform(-0.5, 0.5)
        r = random.random()

        if r > 0.9:
            self.data += delta * 15
        elif r > 0.8: 
            # attraction to the initial value
            delta += (0.5 if self.init > self.data else -0.5)
            self.data += delta
        else:
            self.data += delta

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
                                        size=(45,-1),
                                        value=str(initval1),
                                        style=wx.TE_PROCESS_ENTER)
        self.manual_text2 = wx.TextCtrl(self, -1, 
                                        size=(45,-1),
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
        self.box1.Add(self.desc_text1, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER)
        self.box1.Add(self.manual_text1, flag=wx.ALIGN_RIGHT| wx.ALIGN_CENTER)

        self.box2.Add(self.desc_text2, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER)
        self.box2.Add(self.manual_text2,  flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER)

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
        return [self.value1, self.value2]


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
    title = 'Demo: dynamic matplotlib graph'
    
    def __init__(self):
        wx.Frame.__init__(self, None, -1, self.title)
        
        self.datagen = DataGen()
        self.data = [self.datagen.next()]
        self.data2 = [self.datagen.next()]
        self.paused = False
        
        self.create_menu()
        self.create_status_bar()
        self.create_main_panel()
        
        self.redraw_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_redraw_timer, self.redraw_timer)    
        [Period, Duartion] = self.pulse_control.manual_value()
        self.redraw_timer.Start(int(Period))

    def create_menu(self):
        self.menubar = wx.MenuBar()
        
        menu_file = wx.Menu()
        m_expt = menu_file.Append(-1, "&Save plot\tCtrl-S", "Save plot to file")
        self.Bind(wx.EVT_MENU, self.on_save_plot, m_expt)
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

        self.pulse_control = BoundTextBox(self.panel, -1, "Pulse", "Period", 
                                          "Duration", 1000, 100)

        
        self.pause_button = wx.Button(self.panel, -1, "Pause")
        self.Bind(wx.EVT_BUTTON, self.on_pause_button, self.pause_button)
        self.Bind(wx.EVT_UPDATE_UI, self.on_update_pause_button, self.pause_button)
        
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
        self.hbox1.Add(self.cb_grid, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.cb_xlab, border=5, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        
        self.hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox2.Add(self.xmin_control, border=5, flag=wx.ALL)
        self.hbox2.Add(self.xmax_control, border=5, flag=wx.ALL)
        self.hbox2.AddSpacer(24)
        self.hbox2.Add(self.ymin_control, border=5, flag=wx.ALL)
        self.hbox2.Add(self.ymax_control, border=5, flag=wx.ALL)

        self.hbox3 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox3.Add(self.xmin_control2, border=5, flag=wx.ALL)
        self.hbox3.Add(self.xmax_control2, border=5, flag=wx.ALL)
        self.hbox3.AddSpacer(24)
        self.hbox3.Add(self.ymin_control2, border=5, flag=wx.ALL)
        self.hbox3.Add(self.ymax_control2, border=5, flag=wx.ALL)

        self.hbox4 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox4.Add(self.pulse_control, border=5, flag=wx.ALL)
        
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)        
        self.vbox.Add(self.hbox1, 0, flag=wx.ALIGN_LEFT | wx.TOP)
        self.vbox.Add(self.hbox2, 0, flag=wx.ALIGN_LEFT | wx.TOP)
        self.vbox.Add(self.hbox3, 0, flag=wx.ALIGN_LEFT | wx.TOP)
        self.vbox.Add(self.hbox4, 0, flag=wx.ALIGN_LEFT | wx.TOP)
        
        self.panel.SetSizer(self.vbox)
        self.vbox.Fit(self)
    
    def create_status_bar(self):
        self.statusbar = self.CreateStatusBar()

    def init_plot(self):
        self.dpi = 100
        self.fig = Figure((3.0, 3.0), dpi=self.dpi)

        self.axes = self.fig.add_subplot(211)
        self.axes.set_axis_bgcolor('black')
        self.axes.set_title('Channel 1', size=12)
        

        self.axes2 = self.fig.add_subplot(212)
        self.axes2.set_axis_bgcolor('black')
        self.axes2.set_title('Channel 2', size=12)
        self.axes2.set_xlabel('Time')
        
        #self.axes.set_xticks([])

        pylab.setp(self.axes.get_xticklabels(), fontsize=8)
        pylab.setp(self.axes.get_yticklabels(), fontsize=8)
        
        pylab.setp(self.axes2.get_xticklabels(), fontsize=8)
        pylab.setp(self.axes2.get_yticklabels(), fontsize=8)

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
        pylab.setp(self.axes.get_xticklabels(), 
            visible=self.cb_xlab.IsChecked())

        pylab.setp(self.axes2.get_xticklabels(), 
            visible=self.cb_xlab.IsChecked())
        
        self.plot_data.set_xdata(np.arange(len(self.data)))
        self.plot_data.set_ydata(np.array(self.data))
        
        self.plot_data2.set_xdata(np.arange(len(self.data2)))
        self.plot_data2.set_ydata(np.array(self.data2))
        
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
            self.flash_status_message("Saved to %s" % path)
    
    def on_redraw_timer(self, event):
        # if paused do not add data, but still redraw the plot
        # (to respond to scale modifications, grid change, etc.)
        #
        if not self.paused:
            self.data.append(self.datagen.next())
            self.data2.append(-self.datagen.next())
        self.draw_plot()
        
        [Period, Duration] = self.pulse_control.manual_value()
        if self.redraw_timer.GetInterval() != Period:
            self.redraw_timer.Stop()
            self.redraw_timer.Start(int(Period))
    
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
    app = wx.PySimpleApp()
    app.frame = GraphFrame()
    app.frame.Show()
    app.MainLoop()

