#!/bin/sh
####
# Author: ddavison
# Description: Download the Mac chromedriver into the current directory
####
function downloadchrome {
  #latest=`curl http://chromedriver.storage.googleapis.com/LATEST_RELEASE`
  version="2.9"
  download_location="http://chromedriver.storage.googleapis.com/$version/chromedriver_mac32.zip"
  rm /tmp/chromedriver_mac32.zip
  wget -P /tmp $download_location
  unzip /tmp/chromedriver_mac32.zip -d .
  mv ./chromedriver ./chromedriver.mac
  chmod u+x ./chromedriver.mac
}
downloadchrome
