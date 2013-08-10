%__python setup.py install --root=$RPM_BUILD_ROOT \
                           --optimize=1 --install-scripts=%{_bindir} \
                           --record=INSTALLED_FILES.1st

(while read f; do
  rf="${RPM_BUILD_ROOT}$f"
  if [ -d "$rf" ]; then
    echo "%%dir $f"
  elif [ -e "$rf" ]; then
    echo "$f"
  fi
done) < INSTALLED_FILES.1st > INSTALLED_FILES
