Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  config.vm.network "private_network", type: "dhcp"
  config.vm.synced_folder "./src", "/src", type: "nfs"
  config.vm.provider "virtualbox" do |vb|
    # Display the VirtualBox GUI when booting the machine
    vb.gui = true 
    # Customize the VM:
    vb.memory = "1024"
    vb.cpus = "1"
  end

  config.vm.provision "shell", inline: <<-SHELL
    sudo apt-get update
    sudo apt-get install -y build-essential gawk git m4
    sudo wget https://bootstrap.pypa.io/get-pip.py
    sudo python get-pip.py
    rm get-pip.py
    sudo pip install pyyaml sandboxlib jsonschema requests bottle
    git clone git://git.baserock.org/baserock/baserock/definitions
    git clone git://git.baserock.org/delta/ybd
    echo "base: /src" > ybd/ybd.conf
  SHELL
end