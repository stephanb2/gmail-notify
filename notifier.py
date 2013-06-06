#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Uploaded by juan_grande 2005/02/24 18:38 UTC
# Modified Stephan Bourgeois <stephanb2@hotmail.com> 2013/01/18
__author__ = "Juan Grande, Stephan Bourgeois"
__copyright__ = "Copyright 2005 Juan Grande, 2013 Stephan Bourgeois"
__license__ = "GNU General Public License version 2.0 (GPLv2)"
__version__ = "1.6.2b"
"""
	Gmail Notifier is a Linux/Windows alternative for the notifier program 
	released by Google, it is written in Python and provides an attractive 
	and simple way to check for new mail messages.
"""

import pygtk
pygtk.require('2.0')
import gtk
import time
import os
from egg.trayicon import TrayIcon
import sys
import warnings
import ConfigParser
#import re			# regular expressions
import cgi			# we use cgi.escape instead of regular expressions (SB)
import argparse

import gmailatom
import GmailConfig
import GmailPopupMenu
import xmllangs


#sys.path.insert (0, "/usr/lib/gmail-notify/")
#sys.path.insert (0, "~/bin/gmail-notify/")
BKG_PATH=sys.path[0]+"/img/background.jpg"
ICON_PATH=sys.path[0]+"/img/icon.png"
ICON2_PATH=sys.path[0]+"/img/icon2.png"
#BKG_PATH="/usr/share/apps/gmail-notify/background.jpg"
#ICON_PATH="/usr/share/apps/gmail-notify/icon.png"
#ICON2_PATH="/usr/share/apps/gmail-notify/icon2.png"
POPUP_WIDTH=280
POPUP_HEIGHT=140

def removetags(text):
	raw=text.split("<b>")
	raw2=raw[1].split("</b>")
	final=raw2[0]
	return final

def shortenstring(text,characters):
	if text == None: text = ""
	mainstr=""
	length=0
	splitstr=text.split(" ")
	for word in splitstr:
		length=length+len(word)
		if len(word)>characters:
			if mainstr=="":
				mainstr=word[0:characters]
				break
			else: break
		mainstr=mainstr+word+" "
		if length>characters: break
	return mainstr.strip()

class GmailNotify:

	configWindow = None
	options = None

	def __init__(self):
		self.init=0
		print "Gmail Notifier "+__version__+" ("+time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())+")"
		print "----------"

		# get profile name from command line argument
		parser = argparse.ArgumentParser()
		parser.add_argument("-p", "--profile",
			help="add profile name to config file. Allows to run multiple instances and check multiple accounts.")
		args = parser.parse_args()
		if args.profile==None:
			profileFile = "notifier.conf"
		else:
			profileFile = "notifier-" + args.profile + ".conf"
		print profileFile

		# Configuration window
		self.configWindow = GmailConfig.GmailConfigWindow( profileFile )
		# Reference to global options
		self.options = self.configWindow.options
		# Check if there is a user and password, if not, load config window
		if self.configWindow.no_username_or_password():
			self.configWindow.show()
			# If there's still not a username or password, just exit.
			if self.configWindow.no_username_or_password():
				sys.exit(0)
		# Load selected language
		self.lang = self.configWindow.get_lang()
		print "selected language: "+self.lang.get_name()
		# Creates the main window
		self.window = gtk.Window(gtk.WINDOW_POPUP)
		self.window.set_title(self.lang.get_string(21))
		self.window.set_resizable(1)
		self.window.set_decorated(0)
		self.window.set_keep_above(1)
		self.window.stick()
		self.window.hide()
		# Define some flags
		self.senddown=0
		self.popup=0
		self.newmessages=0
		self.mailcheck=0
		self.hasshownerror=0
		self.hassettimer=0 
		self.dont_connect=0
		self.unreadmsgcount=0
		# Define the timers
		self.maintimer=None
		self.popuptimer=0
		self.waittimer=0
		# Create the tray icon object
		self.tray = TrayIcon(self.lang.get_string(21));
		self.eventbox = gtk.EventBox()
		self.tray.add(self.eventbox)
		self.eventbox.connect("button_press_event", self.tray_icon_clicked)
		# Tray icon drag&drop options
		self.eventbox.drag_dest_set(
			gtk.DEST_DEFAULT_ALL,
			[('_NETSCAPE_URL', 0, 0),('text/uri-list ', 0, 1),('x-url/http', 0, 2)],
			gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
		# Create the tooltip for the tray icon
		self._tooltip = gtk.Tooltips()
		# Set the image for the tray icon
		self.imageicon = gtk.Image()
		pixbuf = gtk.gdk.pixbuf_new_from_file( ICON_PATH )
		scaled_buf = pixbuf.scale_simple(24,24,gtk.gdk.INTERP_BILINEAR)
		self.imageicon.set_from_pixbuf(scaled_buf)
		self.eventbox.add(self.imageicon)
		# Show the tray icon
		self.tray.show_all()
		# Create the popup menu
		self.popup_menu = GmailPopupMenu.GmailPopupMenu( self)
		# Create the popup
		self.fixed=gtk.Fixed()
		self.window.add(self.fixed)
		self.fixed.show()
		self.fixed.set_size_request(0,0)
		# Set popup's background image
		#self.image=gtk.Image()
		#self.image.set_from_file( BKG_PATH )
		#self.image.show()
		#self.fixed.put(self.image,0,0)
		#-----self.window.set_border_width(4)
		self.window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#ddffff'))
		# Set popup's label
		self.label=gtk.Label()
		self.label.set_line_wrap(1)
		self.label.set_size_request(POPUP_WIDTH-20, POPUP_HEIGHT-20)
		#self.label.set_size_request(POPUP_WIDTH-20, -1) #(SB) dynamic height
		self.label.set_alignment(xalign=0, yalign=0) #(SB) align top left
		self.default_label = "<span><b>" + self.lang.get_string(21) + "</b></span>\n" + self.lang.get_string(20)
		self.label.set_markup( self.default_label)
		# Show popup
		self.label.show()
		# Create popup's event box
		self.event_box = gtk.EventBox()
		self.event_box.set_visible_window(0)
		self.event_box.show()
		self.event_box.add(self.label)
		#self.event_box.set_size_request(POPUP_WIDTH, POPUP_HEIGHT)
		self.event_box.set_border_width(10) #(SB) set border around label
		self.event_box.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.event_box.connect("button_press_event", self.event_box_clicked)
		# Setup popup's event box
		self.fixed.add(self.event_box)
		self.event_box.realize()
		self.event_box.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))
		# Resize and move popup's event box
		self.window.resize(POPUP_WIDTH,1)	
		self.width, self.height = self.window.get_size()
		self.height+=self.options['voffset']
		self.width+=self.options['hoffset']
		self.window.move(gtk.gdk.screen_width() - self.width, gtk.gdk.screen_height() - self.height)

		self.init=1
		while gtk.events_pending():
			gtk.main_iteration(gtk.TRUE)
		# Attemp connection for first time
		if self.connect()==1:
			# Check mail for first time
			self.mail_check()

		# Convert "checkinterval" seconds to miliseconds
		self.maintimer=gtk.timeout_add(self.options['checkinterval']*1000,self.mail_check)


	def connect(self):
		# If connecting, cancel connection
		if self.dont_connect==1:
			print "connection attemp suspended"
			return 0
		self.dont_connect=1
		print "connecting..."
		self._tooltip.set_tip(self.tray,self.lang.get_string(13))
		while gtk.events_pending():
			gtk.main_iteration( gtk.TRUE)
		# Attemp connection
		try:
			self.connection=gmailatom.GmailAtom(self.options['gmailusername'],self.options['gmailpassword'],self.options['proxy'])
			self.connection.refreshInfo()
			print "connection successful... continuing"
			self._tooltip.set_tip(self.tray,self.lang.get_string(14))
			self.dont_connect=0
			return 1
		except:
			print "login failed, will retry"
			self._tooltip.set_tip(self.tray,self.lang.get_string(15))
			#self.default_label = "<span size='large' ><u><i>"+self.lang.get_string(15)+"</i></u></span>\n\n"+self.lang.get_string(16)
			self.default_label = "<span size='medium'><b>" + self.lang.get_string(15) + \
					"</b></span>\n <span size='small'>" + self.lang.get_string(16)+"</span>"
			self.label.set_markup(self.default_label)
			self.show_popup()
			self.dont_connect=0
			return 0


	def mail_check(self, event=None):
		# If checking, cancel mail check
		if self.mailcheck==1:
			print "self.mailcheck=1"
			return gtk.TRUE
		# If popup is up, destroy it
		if self.popup==1:
			self.destroy_popup()
		self.mailcheck=1
		print "----------"
		print "checking for new mail ("+time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())+")"
		while gtk.events_pending():
			gtk.main_iteration( gtk.TRUE)

		# Get new messages count
		attrs = self.has_new_messages()

		# If mail check was unsuccessful
		if attrs[0]==-1:
			self.mailcheck=0
			return gtk.TRUE

		# Update tray icon
		self.eventbox.remove(self.imageicon)
		self.imageicon = gtk.Image()
		
		# create label and tooltip content (SB)
		# produce new label if there are unread messages (attrs[0]>0)
		# escape characters from message for HTML, including quotes.
		if attrs[0]>0:		
			sender = attrs[2]
			subject= cgi.escape(attrs[3], True)
			snippet= cgi.escape(attrs[4], True)
			#label header
			self.default_label = "<b>"+self.options['gmailusername']+" ("+ str(attrs[0]) +")\n</b>"
			#label message
			self.default_label += "<span size='small'><b>" + \
					sender[0:24]+" - " + \
					shortenstring(subject,36)+"</b>"
			if len(snippet)>0:
				self.default_label += " - "+snippet+"...</span>"
			else:
				self.default_label += "</span>"
		# display popup if there are new messages
		if attrs[1]>0:
			print str(attrs[1])+" new messages"
			self.show_popup()
		# update tooltip string
		if attrs[0]>0:
			print str(attrs[0])+" unread messages"
			s = ' ' 
			if attrs[0]>1: s=self.lang.get_string(35)+" "
			self._tooltip.set_tip(self.tray,(self.lang.get_string(19))%{'u':attrs[0],'s':s})
			pixbuf = gtk.gdk.pixbuf_new_from_file( ICON2_PATH )
		else:
			print "no new messages"
			#self.default_label="<b>"+self.lang.get_string(21)+"</b>\n"+self.lang.get_string(18)
			self.default_label = "<b>"+self.options['gmailusername']+" ("+ str(attrs[0]) +")\n</b>"
			self.default_label+=self.lang.get_string(18)
			self._tooltip.set_tip(self.tray,self.lang.get_string(18))	
			pixbuf = gtk.gdk.pixbuf_new_from_file( ICON_PATH )
			
		# using regular expressions will not always work. (SB)
		# more characters than "&" need to be escaped. use cgi.escape(string) instead
		#p = re.compile('&')
		#self.label.set_markup(p.sub('&amp;', self.default_label))
		self.label.set_markup(self.default_label)
		scaled_buf = pixbuf.scale_simple(24,24,gtk.gdk.INTERP_BILINEAR)
		self.imageicon.set_from_pixbuf(scaled_buf)
		self.eventbox.add(self.imageicon)
		self.tray.show_all()
		self.unreadmsgcount=attrs[0]
		
		self.mailcheck=0

		return gtk.TRUE

	
	def has_new_messages(self):
		unreadmsgcount=0
		# Get total messages in inbox
		try:
			self.connection.refreshInfo()
			unreadmsgcount=self.connection.getUnreadMsgCount()
		except:
			# If an error ocurred, cancel mail check
			print "getUnreadMsgCount() failed, will try again soon"
			return (-1,)

		sender=''
		subject=''
		snippet=''
		finalsnippet=''
		if unreadmsgcount>0:
			# Get latest message data
			sender = self.connection.getMsgAuthorName(0)
			subject = self.connection.getMsgTitle(0)
			snippet = self.connection.getMsgSummary(0)
			#FIXME: maybe count total number of characters?
			if len(sender)>12: 
				finalsnippet=shortenstring(snippet,70)
			else:
				finalsnippet=shortenstring(snippet,80)
		# Really new messages? Or just repeating...
		newmsgcount=unreadmsgcount-self.unreadmsgcount
		self.unreadmsgcount=unreadmsgcount
		if unreadmsgcount>0:
			return (unreadmsgcount, newmsgcount, sender, subject, finalsnippet)
		else:
			return (unreadmsgcount, 0, sender, subject, finalsnippet)


	def show_popup(self):
		# If popup is up, destroy it
		if self.popup==1:
			self.destroy_popup()
		# Generate popup
		print "generating popup"
		self.popuptimer = gtk.timeout_add(self.options['animationdelay'],self.popup_proc)
		self.window.show()	
		return


	def destroy_popup(self):
		print "destroying popup"
		if self.popuptimer>0:gtk.timeout_remove(self.popuptimer)
		if self.waittimer>0: gtk.timeout_remove(self.waittimer)
		self.senddown=0
		self.hassettimer=0
		self.window.hide()
		self.window.resize(POPUP_WIDTH,1)
		self.window.move(gtk.gdk.screen_width() - self.width, gtk.gdk.screen_height() - self.height)
		return


	def popup_proc(self):
		# Set popup status flag
		if self.popup==0:
			self.popup=1
		currentsize=self.window.get_size()
		currentposition=self.window.get_position()
		positiony=currentposition[1]
		sizex=currentsize[0]
		sizey=currentsize[1]
		if self.senddown==1:
			if sizey<2:
				# If popup is down
				self.senddown=0
				self.window.hide()
				self.window.resize(sizex, 1)
				self.window.move(gtk.gdk.screen_width() - self.width, gtk.gdk.screen_height() - self.height)
				self.popup=0
				return gtk.FALSE
			else:
				# Move it down
				self.window.resize(sizex, sizey-2)	
				self.window.move(gtk.gdk.screen_width() - self.width,positiony+2)
		else:
			if sizey<140:
				# Move it up
				self.window.resize(sizex, sizey+2)
				self.window.move(gtk.gdk.screen_width() - self.width,positiony-2)
			else:
				# If popup is up, run wait timer. Convert seconds to miliseconds (SB)
				sizex=currentsize[0]
				self.popup=1
				if self.hassettimer==0:
					self.waittimer = gtk.timeout_add(self.options['popuptimespan']*1000,self.wait)
					self.hassettimer=1	
		return gtk.TRUE


	def wait(self):
		self.senddown=1
		self.hassettimer=0
		return gtk.FALSE


	def tray_icon_clicked(self,signal,event):
		if event.button==3:
			self.popup_menu.show_menu(event)
		else:
			self.label.set_markup(self.default_label)
			self.show_popup()


	def event_box_clicked(self,signal,event):
		if event.button==1:
			self.gotourl()

	def exit(self, event):
		dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, self.lang.get_string(5))
		dialog.width, dialog.height = dialog.get_size()
		dialog.move( gtk.gdk.screen_width()/2-dialog.width/2, gtk.gdk.screen_height()/2-dialog.height/2)
		ret = dialog.run()
		if( ret==gtk.RESPONSE_YES):
			gtk.main_quit(0)
		dialog.destroy()


	def gotourl( self, wg=None):
		print "----------"
		print "launching browser "+self.options['browserpath']+" http://mail.google.com"
		os.system(self.options['browserpath']+" http://mail.google.com &")	


	def show_quota_info( self, event):
		print "Not available"
		#if self.popup==1:self.destroy_popup()
		#print "----------"
		#print "retrieving quota info"
		#while gtk.events_pending()!=0:
		#	gtk.main_iteration(gtk.TRUE)
		#try:
		#	usage=self.connection.getQuotaInfo()
		#except:
		#	if self.connect()==0:
		#		return
		#	else:
		#		usage=self.connection.getQuotaInfo()
		#self.label.set_markup("<span size='large' ><u><i>"+self.lang.get_string(6)+"</i></u></span>\n\n"+self.lang.get_string(24)%{'u':usage[0],'t':usage[1],'p':usage[2]})
		#self.show_popup()


	def update_config(self, event=None):
		# Kill all timers
		if self.popup==1:self.destroy_popup()
		if self.init==1:gtk.timeout_remove(self.maintimer)
		# Run the configuration dialog
		self.configWindow.show()

		# Update timeout. Convert seconds to miliseconds (SB)
		self.maintimer = gtk.timeout_add(self.options["checkinterval"]*1000, self.mail_check )

		# Update user/pass
		self.connection=gmailatom.GmailAtom(self.options["gmailusername"],self.options["gmailpassword"],self.options['proxy'])
		self.connect()
		self.mail_check()

		# Update popup location
		self.window.resize(POPUP_WIDTH,1)
		self.width, self.height = self.window.get_size()
		self.height +=self.options["voffset"]
		self.width +=self.options["hoffset"]
		self.window.move(gtk.gdk.screen_width() - self.width, gtk.gdk.screen_height() - self.height)

		# Update language
		self.lang=self.configWindow.get_lang()	

		# Update popup menu
		self.popup_menu = GmailPopupMenu.GmailPopupMenu(self)

		return


	def main(self):
		gtk.main()



if __name__ == "__main__":
	warnings.filterwarnings( action="ignore", category=DeprecationWarning)
	gmailnotifier = GmailNotify()
	gmailnotifier.main()
