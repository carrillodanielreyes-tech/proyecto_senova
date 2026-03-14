from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
import re
from django.contrib.auth.models import User, Group
import logging
import traceback
from django.db import transaction, IntegrityError
from Gesicom.models import Envio
import datetime
from django.db.models import Count
import json

logger = logging.getLogger(__name__)


ROLE_ROUTES = {
	'instructor': 'role_instructor',
	'investigador': 'role_investigador',
	'dinamizador': 'role_dinamizador',
	'coordinador': 'role_coordinador',
	'usuario': 'usuario',
}


def _validar_contraseña(contraseña1, contraseña2=None):
	errores = []

	if not contraseña1:
		errores.append('La contraseña es obligatoria.')
		return errores

	if contraseña2 and contraseña1 != contraseña2:
		errores.append('Las contraseñas no coinciden.')
		return errores

	if len(contraseña1) != 8:
		errores.append('La contraseña debe tener exactamente 8 caracteres.')

	tiene_mayuscula = re.search(r'[A-Z]', contraseña1) is not None
	tiene_digito = re.search(r'\d', contraseña1) is not None
	tiene_especial = re.search(r'[!@#$%^&*(),.?":{}|<>]', contraseña1) is not None

	if not tiene_mayuscula:
		errores.append('Debe contener al menos una letra mayúscula.')

	if not (tiene_digito or tiene_especial):
		errores.append('Debe contener al menos un número o carácter especial.')

	return errores


def login_view(request):
	rol = request.GET.get('role') or request.POST.get('role') or ''
	if rol not in ROLE_ROUTES:
		rol = ''

	# Mostrar mensaje de cuenta creada si viene el parámetro ?created=1
	success_msg = None
	if request.method == 'GET' and request.GET.get('created'):
		success_msg = 'Cuenta creada correctamente. Por favor inicia sesión.'

	if request.method == 'POST':
		entrada_usuario = (request.POST.get('username', '') or '').strip()
		contraseña = request.POST.get('password', '')
		recordar = request.POST.get('remember')

		# Si el usuario escribió un correo, intentar resolver su nombre de usuario
		usuario_para_auth = entrada_usuario
		if '@' in entrada_usuario and not User.objects.filter(username=entrada_usuario).exists():
			try:
				u = User.objects.get(email__iexact=entrada_usuario)
				usuario_para_auth = u.username
			except User.DoesNotExist:
				# no existe un usuario con ese correo
				pass

		usuario = authenticate(request, username=usuario_para_auth, password=contraseña)
		if usuario is not None:
			login(request, usuario)
			if recordar:
				request.session.set_expiry(60 * 60 * 24 * 14)
			else:
				request.session.set_expiry(0)
			if usuario.is_superuser:
				return redirect('admin:index')

			grupos_usuario = set(usuario.groups.values_list('name', flat=True))

			if 'administrador' in grupos_usuario:
				return redirect('admin_menu')

			if rol and rol in ROLE_ROUTES:
				return redirect(ROLE_ROUTES[rol])

			destino = 'usuario' if 'usuario' in grupos_usuario else 'home'
			return redirect(destino)

		return render(request, 'login.html', {
			'error': 'Usuario o contraseña incorrectos',
			'role': rol,
			'username': entrada_usuario,
		})

	# Si no es POST (GET), mostrar la plantilla y el posible mensaje de cuenta creada
	context = {'role': rol}
	if success_msg:
		context['success'] = success_msg
	return render(request, 'login.html', context)


def register_view(request):
	rol = request.GET.get('role') or request.POST.get('role') or ''
	if request.method == 'POST':
		# Log de depuración: capturar los datos enviados por la interfaz
		try:
			logger.debug('register_view POST data: %s', dict(request.POST))
		except Exception:
			logger.exception('No se pudo serializar request.POST')
		nombre_usuario = (request.POST.get('username', '') or '').strip()
		correo = (request.POST.get('email', '') or '').strip().lower()
		contraseña1 = request.POST.get('password1', '')
		contraseña2 = request.POST.get('password2', '')

		errores = []
		if not nombre_usuario:
			errores.append('El usuario es obligatorio.')
		if not correo:
			errores.append('El correo es obligatorio.')

		errores.extend(_validar_contraseña(contraseña1, contraseña2))

		if User.objects.filter(username=nombre_usuario).exists():
			errores.append('Ese usuario ya existe. Prueba con otro.')

		if User.objects.filter(email=correo).exists():
			errores.append('Ese correo ya está registrado.')

		if errores:
			return render(request, 'register.html', {
				'errores': errores,
				'rol': rol,
				'nombre_usuario': nombre_usuario,
				'correo': correo,
			})

		try:
			with transaction.atomic():
				usuario = User.objects.create_user(username=nombre_usuario, email=correo, password=contraseña1)
				g, _ = Group.objects.get_or_create(name='usuario')
				usuario.groups.add(g)
				usuario.save()
				logger.info('Usuario creado desde register_view: %s (pk=%s)', usuario.username, getattr(usuario, 'pk', None))
				# No iniciamos sesión automáticamente: redirigir al inicio de sesión con indicador 'created'
				return redirect('/login/?created=1')
		except IntegrityError:
			errores.append('El usuario o correo ya existe.')
			return render(request, 'register.html', {
				'errores': errores,
				'rol': rol,
				'nombre_usuario': nombre_usuario,
				'correo': correo,
			})
		except Exception:
			tb = traceback.format_exc()
			logger.exception('Error creando usuario')
			errores.append('Error interno al crear la cuenta. Contacta al administrador.')
			return render(request, 'register.html', {
				'errores': errores,
				'rol': rol,
				'nombre_usuario': nombre_usuario,
				'correo': correo,
				'rastreo_debug': tb,
			})

	return render(request, 'register.html', {'rol': rol})


@login_required(login_url='login')
def panel_usuario(request):
	"""Vista del panel personal del usuario."""
	# Calcular métricas simples para el resumen de reportes
	consulta = Envio.objects.all()
	total_envios = consulta.count()
	hoy = datetime.date.today()
	desde_30 = hoy - datetime.timedelta(days=30)
	nuevas_30d = consulta.filter(fecha_envio__gte=desde_30).count()
	aprobadas = consulta.filter(aprobada=True).count()
	aprobadas_30d = consulta.filter(aprobada=True, fecha_envio__gte=desde_30).count()

	# Datos por categoría (si existen elecciones en el modelo)
	categorias_labels = []
	categorias_data = []
	if hasattr(Envio, 'PROYECTO_CHOICES'):
		proyectos_guardados = set(Envio.objects.values_list('proyecto', flat=True))
		for code, label in Envio.PROYECTO_CHOICES:
			if code and code in proyectos_guardados:
				categorias_labels.append(label)
				categorias_data.append(consulta.filter(proyecto=code).count())

	# Trimestres (por defecto 4)
	num_quarters = 4
	trimestres_labels = []
	datos_trimestrales_nuevas = []
	datos_trimestrales_aprobadas = []
	current_year = hoy.year
	current_quarter = (hoy.month - 1) // 3 + 1
	q_list = []
	y = current_year
	q = current_quarter
	for _ in range(num_quarters):
		q_list.insert(0, (y, q))
		q -= 1
		if q == 0:
			q = 4
			y -= 1
	for (y, q) in q_list:
		start_month = (q - 1) * 3 + 1
		start_date = datetime.date(y, start_month, 1)
		end_month = start_month + 2
		# calcular último día del mes
		if end_month == 12:
			end_day = 31
		else:
			next_month = end_month + 1
			end_day = (datetime.date(y, next_month, 1) - datetime.timedelta(days=1)).day
		end_date = datetime.date(y, end_month, end_day)
		trimestres_labels.append(f"Q{q} {y}")
		datos_trimestrales_nuevas.append(consulta.filter(fecha_envio__gte=start_date, fecha_envio__lte=end_date).count())
		datos_trimestrales_aprobadas.append(consulta.filter(fecha_envio__gte=start_date, fecha_envio__lte=end_date, aprobada=True).count())

	# Top usuarios
	top_users_qs = consulta.values('usuario__first_name', 'usuario__last_name', 'usuario__username').annotate(total=Count('id')).order_by('-total')[:6]
	usuarios_labels = []
	usuarios_data = []
	for u in top_users_qs:
		name = u.get('usuario__first_name') or u.get('usuario__username') or 'Usuario'
		if u.get('usuario__last_name'):
			name = f"{name} {u.get('usuario__last_name')}"
		usuarios_labels.append(name)
		usuarios_data.append(u['total'])

	context = {
		'total_envios': total_envios,
		'nuevas_30d': nuevas_30d,
		'aprobadas': aprobadas,
		'aprobadas_30d': aprobadas_30d,
		'categorias_labels_json': json.dumps(categorias_labels, ensure_ascii=False),
		'categorias_data_json': json.dumps(categorias_data),
		'trimestres_labels_json': json.dumps(trimestres_labels, ensure_ascii=False),
		'datos_trimestrales_nuevas_json': json.dumps(datos_trimestrales_nuevas),
		'datos_trimestrales_aprobadas_json': json.dumps(datos_trimestrales_aprobadas),
		'usuarios_labels_json': json.dumps(usuarios_labels, ensure_ascii=False),
		'usuarios_data_json': json.dumps(usuarios_data),
	}
	return render(request, 'usuario/panel_usuario.html', context)


def logout_view(request):
	"""Cerrar sesión del usuario."""
	logout(request)
	return redirect('login')

