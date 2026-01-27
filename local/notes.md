gcloud auth login --login-config="gcloud.json" --no-launch-browser

gcloud config set project brk-prj-salvador-dura-bern-sbx
gcloud auth application-default set-quota-project brk-prj-salvador-dura-bern-sbx

zsh gcloud_env.zsh
