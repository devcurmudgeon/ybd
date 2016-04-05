Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  config.vm.network "private_network", type: "dhcp"
  config.vm.synced_folder ".", "/src/ybd"
  config.vm.provider "virtualbox" do |vb|
    # Display the VirtualBox GUI when booting the machine
    # vb.gui = true
    # Customize the VM:
    vb.memory = "1024"
    vb.cpus = "1"
  end

  config.vm.provision "shell", inline: <<-SHELL
    cd /src
    ./ybd/install_dependencies.sh
    git clone git://git.baserock.org/baserock/baserock/definitions
    echo "base: /src" > ybd/ybd.conf
  SHELL
end
