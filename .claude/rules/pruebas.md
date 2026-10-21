# Pruebas

- Correr `.venv/bin/python -m pytest` después de cada cambio de código y antes de cualquier commit. Si algo falla, avisarlo; no commitear con pruebas rotas.
- Todo comportamiento nuevo de la API lleva pruebas en `tests/`, en el archivo del área que corresponda. Los nombres de las pruebas van en español y describen la regla (`test_un_comercio_no_ve_ni_carga_pases_de_otro`).
- Usar los fixtures de `tests/conftest.py` (`client`, `db`, `make_business`, `login`, `register`, `make_pass`, `wallet`) en lugar de armar datos a mano.
- Las pruebas nunca tocan `sello.db` ni salen a internet. Si un módulo nuevo importa directamente una función que habla con Google (`sync_business_passes`, `update_google_wallet_pass`, `generate_google_wallet_url`), hay que parchearla también en el fixture `wallet`; si no, la protección hace fallar la prueba con "intentó conectarse a Google Wallet".
- Para probar en el navegador sin ensuciar la base del usuario, levantar una copia del proyecto en una carpeta temporal, con su propia `sello.db`, en otro puerto.
