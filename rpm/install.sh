%define mangledname %(echo "%{name}" | tr - _)

%__python setup.py install --root=$RPM_BUILD_ROOT \
                           --optimize=1 --install-scripts=%{_bindir} \
                           --record=INSTALLED_FILES.1st

rm -rf $RPM_BUILD_ROOT%{python_sitelib}/%{mangledname}-*
%__grep -v %{mangledname} INSTALLED_FILES.1st > INSTALLED_FILES
