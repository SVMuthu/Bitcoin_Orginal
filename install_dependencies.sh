#!/bin/bash

# Update package lists
sudo apt-get update

# Install essential build tools
sudo apt-get install -y build-essential

# Install Autotools and other necessary build tools
sudo apt-get install -y autoconf automake libtool pkg-config

# Install Berkeley DB (BDB) dependencies
sudo apt-get install -y libdb4.8-dev libdb4.8++-dev  # For BDB 4.8
# sudo apt-get install -y libdb5.1-dev libdb5.1++-dev  # For BDB 5.1 (uncomment if needed)

# Install OpenSSL
sudo apt-get install -y libssl-dev

# Install Boost Libraries
sudo apt-get install -y libboost-all-dev

# Install Qt and other GUI dependencies
sudo apt-get install -y qtbase5-dev libqt5gui5 libqt5core5a libqt5dbus5
sudo apt-get install -y libqt5webkit5-dev qttools5-dev-tools

# Install additional dependencies
sudo apt-get install -y libevent-dev
sudo apt-get install -y libzmq3-dev
sudo apt-get install -y libunivalue-dev

# Optional dependencies
sudo apt-get install -y libminiupnpc-dev
sudo apt-get install -y libqrencode-dev

# Print a message indicating that the installation is complete
echo "All dependencies installed. You can now proceed with building Bitcoin Core."
