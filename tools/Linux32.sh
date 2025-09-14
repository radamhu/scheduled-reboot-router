#!/bin/sh
####
# Author: ddavison
# Description: Download the Linux chromedriver into the current directory
####
function downloadchrome {
  # latest=`curl http://chromedriver.storage.googleapis.com/LATEST_RELEASE`
  version="2.9"
  download_location="http://chromedriver.storage.googleapis.com/$version/chromedriver_linux32.zip"
  rm /tmp/chromedriver_linux32.zip
  wget -P /tmp $download_location
  unzip /tmp/chromedriver_linux32.zip -d .
  mv ./chromedriver ./chromedriver.linux
  chmod u+x ./chromedriver.linux
}
downloadchrome
