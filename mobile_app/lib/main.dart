import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const PlantApp());
}

class AppConfig extends InheritedWidget {
  const AppConfig({
    super.key,
    required this.baseUrl,
    required this.token,
    required this.isAdmin,
    required super.child,
  });

  final String baseUrl;
  final String token;
  final bool isAdmin;

  static AppConfig? of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppConfig>();

  @override
  bool updateShouldNotify(AppConfig oldWidget) =>
      baseUrl != oldWidget.baseUrl ||
      token != oldWidget.token ||
      isAdmin != oldWidget.isAdmin;
}

class PlantApp extends StatefulWidget {
  const PlantApp({super.key});
  @override
  State<PlantApp> createState() => _PlantAppState();
}

class _PlantAppState extends State<PlantApp> {
  bool _hydrating = true;
  String? _baseUrl = null;
  String _token = "";
  bool _isAdmin = false;

  @override
  void initState() {
    super.initState();
    _loadSavedSession();
  }

  Future<void> _loadSavedSession() async {
    final prefs = await SharedPreferences.getInstance();
    final base = prefs.getString('baseUrl');
    final token = prefs.getString('token');
    final isAdmin = prefs.getBool('isAdmin');
    if (base != null && base.isNotEmpty && token != null && token.isNotEmpty) {
      setState(() {
        _baseUrl = base;
        _token = token;
        _isAdmin = isAdmin ?? false;
      });
    }
    setState(() {
      _hydrating = false;
    });
  }

  Future<void> _saveSession(String base, String token, bool isAdmin) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('baseUrl', base);
    await prefs.setString('token', token);
    await prefs.setBool('isAdmin', isAdmin);
  }

  void _logout() {
    setState(() {
      _baseUrl = null;
      _token = "";
      _isAdmin = false;
    });
    SharedPreferences.getInstance().then((prefs) {
      prefs.remove('baseUrl');
      prefs.remove('token');
      prefs.remove('isAdmin');
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_hydrating) {
      return MaterialApp(
        title: 'Plant Automation',
        theme: ThemeData(
          brightness: Brightness.light,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF16a34a),
            brightness: Brightness.light,
          ),
        ),
        home: const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    final theme = ThemeData(
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF16a34a),
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: const Color(0xFFf8fafc),
      cardColor: Colors.white,
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
      ),
    );

    final home = (_baseUrl == null)
        ? LoginScreen(
            onLogin: (base, token, isAdmin) async {
              setState(() {
                _baseUrl = base;
                _token = token;
                _isAdmin = isAdmin;
              });
              await _saveSession(base, token, isAdmin);
            },
          )
        : AppConfig(
            baseUrl: _baseUrl!,
            token: _token,
            isAdmin: _isAdmin,
            child: HomeShell(onLogout: _logout),
          );

    return MaterialApp(
      title: 'Plant Automation',
      theme: theme,
      home: home,
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.onLogout});
  final VoidCallback onLogout;
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  String _getBuildDate() {
    final now = DateTime.now();
    return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')} ${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      const DeviceListScreen(),
      const AlertsScreen(),
      const ClaimScreen(),
    ];
    final titles = ['Devices', 'Alerts', 'Claim'];
    return Scaffold(
      appBar: AppBar(
        title: Text(titles[_index], style: const TextStyle(color: Colors.black)),
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline),
            onPressed: () {
              showDialog(
                context: context,
                builder: (context) => AlertDialog(
                  title: const Text('Plant Automation'),
                  content: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Mobile app for plant monitoring and automation'),
                      const SizedBox(height: 12),
                      Text('Build: ${_getBuildDate()}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                    ],
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Close'),
                    ),
                  ],
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: widget.onLogout,
            tooltip: 'Sign out',
          ),
        ],
      ),
      body: SafeArea(child: pages[_index]),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Colors.white,
        selectedItemColor: const Color(0xFF16a34a),
        unselectedItemColor: Colors.grey.shade500,
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.devices), label: "Devices"),
          BottomNavigationBarItem(icon: Icon(Icons.warning_amber_rounded), label: "Alerts"),
          BottomNavigationBarItem(icon: Icon(Icons.link), label: "Claim"),
        ],
      ),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.onLogin});
  final void Function(String baseUrl, String token, bool isAdmin) onLogin;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _baseController = TextEditingController(text: 'https://rt.329.run:8443');
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _submitting = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFf8fafc),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Plant Automation',
                        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF16a34a)),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Sign in to your backend',
                        style: TextStyle(color: Color(0xFF64748b)),
                      ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _baseController,
                          decoration: const InputDecoration(
                            labelText: 'Base URL',
                            hintText: 'http://192.168.x.x:8000',
                            filled: true,
                          ),
                          validator: (v) => (v == null || v.isEmpty) ? 'Base URL required' : null,
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _emailController,
                          decoration: const InputDecoration(
                            labelText: 'Email',
                            hintText: 'you@example.com',
                            filled: true,
                          ),
                          validator: (v) => (v == null || v.isEmpty) ? 'Email required' : null,
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _passwordController,
                          obscureText: true,
                          decoration: const InputDecoration(
                            labelText: 'Password',
                            filled: true,
                          ),
                          validator: (v) => (v == null || v.isEmpty) ? 'Password required' : null,
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.red.shade50,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.red.shade200),
                            ),
                            child: Text(_error!, style: TextStyle(color: Colors.red.shade700)),
                          ),
                        ],
                        const SizedBox(height: 16),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF16a34a),
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            ),
                            onPressed: _submitting
                                ? null
                                : () async {
                                    if (!_formKey.currentState!.validate()) return;
                                    setState(() {
                                      _submitting = true;
                                      _error = null;
                                    });
                                    try {
                                      final result = await ApiClient.login(
                                        _baseController.text.trim(),
                                        _emailController.text.trim(),
                                        _passwordController.text,
                                      );
                                      widget.onLogin(
                                        _baseController.text.trim(),
                                        result.token,
                                        result.isAdmin,
                                      );
                                    } catch (e) {
                                      setState(() {
                                        _error = 'Login failed: $e';
                                      });
                                    } finally {
                                      setState(() {
                                        _submitting = false;
                                      });
                                    }
                                  },
                            child: _submitting
                                ? const SizedBox(
                                    height: 20,
                                    width: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Text('Sign in'),
                          ),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Text('Don\'t have an account? ', style: TextStyle(color: Color(0xFF64748b))),
                            TextButton(
                              onPressed: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => RegisterScreen(
                                      baseUrl: _baseController.text.trim(),
                                      onRegister: (baseUrl, token, isAdmin) {
                                        widget.onLogin(baseUrl, token, isAdmin);
                                        Navigator.pop(context);
                                      },
                                    ),
                                  ),
                                );
                              },
                              child: const Text('Register', style: TextStyle(color: Color(0xFF16a34a), fontWeight: FontWeight.bold)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Center(
                          child: Text(
                            'Build: ${_getBuildDate()}',
                            style: const TextStyle(fontSize: 11, color: Color(0xFF94a3b8)),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
    );
  }

  String _getBuildDate() {
    final now = DateTime.now();
    return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')} ${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')}';
  }
}

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key, required this.baseUrl, required this.onRegister});
  final String baseUrl;
  final void Function(String baseUrl, String token, bool isAdmin) onRegister;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _submitting = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFf8fafc),
      appBar: AppBar(
        backgroundColor: const Color(0xFFf8fafc),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Create Account',
                        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF16a34a)),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Register to get started',
                        style: TextStyle(color: Color(0xFF64748b)),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _emailController,
                        decoration: const InputDecoration(
                          labelText: 'Email',
                          hintText: 'you@example.com',
                          filled: true,
                        ),
                        keyboardType: TextInputType.emailAddress,
                        validator: (v) {
                          if (v == null || v.isEmpty) return 'Email required';
                          if (!v.contains('@')) return 'Invalid email';
                          return null;
                        },
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'Password',
                          filled: true,
                        ),
                        validator: (v) {
                          if (v == null || v.isEmpty) return 'Password required';
                          if (v.length < 8) return 'Password must be at least 8 characters';
                          return null;
                        },
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _confirmPasswordController,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'Confirm Password',
                          filled: true,
                        ),
                        validator: (v) {
                          if (v == null || v.isEmpty) return 'Please confirm password';
                          if (v != _passwordController.text) return 'Passwords do not match';
                          return null;
                        },
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.red.shade50,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.red.shade200),
                          ),
                          child: Text(_error!, style: TextStyle(color: Colors.red.shade700)),
                        ),
                      ],
                      const SizedBox(height: 16),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF16a34a),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                          onPressed: _submitting
                              ? null
                              : () async {
                                  if (!_formKey.currentState!.validate()) return;
                                  setState(() {
                                    _submitting = true;
                                    _error = null;
                                  });
                                  try {
                                    final result = await ApiClient.register(
                                      widget.baseUrl,
                                      _emailController.text.trim(),
                                      _passwordController.text,
                                    );
                                    widget.onRegister(
                                      widget.baseUrl,
                                      result.token,
                                      result.isAdmin,
                                    );
                                  } catch (e) {
                                    setState(() {
                                      _error = 'Registration failed: $e';
                                    });
                                  } finally {
                                    setState(() {
                                      _submitting = false;
                                    });
                                  }
                                },
                          child: _submitting
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                )
                              : const Text('Create Account'),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text('Already have an account? ', style: TextStyle(color: Color(0xFF64748b))),
                          TextButton(
                            onPressed: () => Navigator.pop(context),
                            child: const Text('Sign in', style: TextStyle(color: Color(0xFF16a34a), fontWeight: FontWeight.bold)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class DeviceListScreen extends StatefulWidget {
  const DeviceListScreen({super.key});
  @override
  State<DeviceListScreen> createState() => _DeviceListScreenState();
}

class _DeviceListScreenState extends State<DeviceListScreen> {
  late Future<List<Device>> _future;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    // Start automatic polling every 60 seconds (matching web UI behavior)
    _pollTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      if (mounted) {
        final cfg = AppConfig.of(context)!;
        setState(() {
          _future = ApiClient(cfg.baseUrl, cfg.token).fetchDevices();
        });
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final cfg = AppConfig.of(context)!;
    _future = ApiClient(cfg.baseUrl, cfg.token).fetchDevices();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cfg = AppConfig.of(context)!;
    return FutureBuilder<List<Device>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ErrorState(
              message: 'Could not load devices',
              detail: snapshot.error.toString(),
              onRetry: () {
                setState(() {
                  _future = ApiClient(cfg.baseUrl, cfg.token).fetchDevices();
                });
              },
            );
          }
          final devices = snapshot.data ?? [];
          if (devices.isEmpty) {
            return const Center(child: Text('No devices yet.'));
          }
          return RefreshIndicator(
            onRefresh: () async {
              setState(() {
                _future = ApiClient(cfg.baseUrl, cfg.token).fetchDevices();
              });
              await _future;
            },
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(12),
              itemCount: devices.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final d = devices[index];
                const offlineThresholdSeconds = 120; // match backend/web default
                final lastSeen = d.lastSeen != null ? DateTime.tryParse(d.lastSeen!) : null;

                // Debug logging
                print('Device: ${d.name}');
                print('  lastSeen string: ${d.lastSeen}');
                print('  lastSeen parsed: $lastSeen');
                print('  status field: ${d.status}');

                final connected = () {
                  if (lastSeen != null) {
                    final age = DateTime.now().toUtc().difference(lastSeen.toUtc());
                    print('  age: ${age.inSeconds} seconds');
                    if (age.inSeconds <= offlineThresholdSeconds) {
                      print('  -> ONLINE (by lastSeen)');
                      return true;
                    }
                  }
                  final status = d.status.toLowerCase();
                  final result = status.contains('active') || status.contains('online');
                  print('  -> ${result ? "ONLINE" : "OFFLINE"} (by status field)');
                  return result;
                }();
                return Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => AppConfig(
                          baseUrl: cfg.baseUrl,
                          token: cfg.token,
                          isAdmin: cfg.isAdmin,
                          child: DeviceDetailScreen(deviceId: d.id, name: d.name),
                        ),
                      ),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                        Container(
                          width: 50,
                          height: 50,
                          decoration: BoxDecoration(
                            color: connected ? const Color(0xFF16a34a).withOpacity(0.12) : Colors.grey.shade200,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(
                            Icons.local_florist_rounded,
                            color: connected ? const Color(0xFF16a34a) : Colors.grey,
                            size: 28,
                          ),
                        ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  d.name,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  d.model ?? 'Unknown model',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: Colors.grey.shade600,
                                  ),
                                ),
                                if (lastSeen != null) ...[
                                  const SizedBox(height: 4),
                                  Text(
                                    'Last seen: ${_formatTimeSince(lastSeen)}',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.grey.shade500,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              _StatusPill(
                                text: connected ? 'Online' : 'Offline',
                                color: connected ? Colors.green : Colors.grey,
                              ),
                              if (cfg.isAdmin) ...[
                                const SizedBox(height: 8),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline, size: 20),
                                  color: Colors.red.shade400,
                                  constraints: const BoxConstraints(),
                                  padding: EdgeInsets.zero,
                                  onPressed: () async {
                                    final confirmed = await showDialog<bool>(
                                          context: context,
                                          builder: (ctx) => AlertDialog(
                                            title: const Text('Delete device'),
                                            content: Text('Delete ${d.name}?'),
                                            actions: [
                                              TextButton(
                                                  onPressed: () => Navigator.pop(ctx, false),
                                                  child: const Text('Cancel')),
                                              TextButton(
                                                  onPressed: () => Navigator.pop(ctx, true),
                                                  child: const Text('Delete')),
                                            ],
                                          ),
                                        ) ??
                                        false;
                                    if (!confirmed) return;
                                    try {
                                      await ApiClient(cfg.baseUrl, cfg.token).deleteDevice(d.id);
                                      setState(() {
                                        _future = ApiClient(cfg.baseUrl, cfg.token).fetchDevices();
                                      });
                                    } catch (_) {}
                                  },
                                ),
                              ],
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
    );
  }
}

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  late Future<List<DeviceAlert>> _future;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final cfg = AppConfig.of(context)!;
    _future = ApiClient(cfg.baseUrl, cfg.token).fetchAlerts();
  }

  Color _severityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return Colors.redAccent;
      case 'WARN':
        return Colors.orangeAccent;
      default:
        return Colors.blueGrey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = AppConfig.of(context)!;
    return FutureBuilder<List<DeviceAlert>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ErrorState(
              message: 'Could not load alerts',
              detail: snapshot.error.toString(),
              onRetry: () {
                setState(() {
                  _future = ApiClient(cfg.baseUrl, cfg.token).fetchAlerts();
                });
              },
            );
          }
          final alerts = snapshot.data ?? [];
          if (alerts.isEmpty) {
            return const Center(child: Text('No alerts.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: alerts.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              final a = alerts[index];
              return Card(
                color: const Color(0xFF111827),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            a.type,
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: _severityColor(a.severity),
                            ),
                          ),
                          Text(
                            a.createdAt ?? '',
                            style: const TextStyle(color: Colors.white60, fontSize: 12),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(a.message, style: const TextStyle(color: Colors.white70)),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Device: ${a.deviceId}',
                            style: const TextStyle(color: Colors.white54, fontSize: 12),
                          ),
                          if (a.resolvedAt == null)
                            TextButton(
                              onPressed: () async {
                                try {
                                  await ApiClient(cfg.baseUrl, cfg.token).resolveAlert(a.id);
                                  setState(() {
                                    _future = ApiClient(cfg.baseUrl, cfg.token).fetchAlerts();
                                  });
                                } catch (_) {}
                              },
                              child: const Text('Resolve'),
                            )
                          else
                            const Text(
                              'Resolved',
                              style: TextStyle(color: Colors.greenAccent, fontSize: 12),
                            ),
                        ],
                      )
                    ],
                  ),
                ),
              );
            },
          );
        },
    );
  }
}

class ClaimScreen extends StatefulWidget {
  const ClaimScreen({super.key});
  @override
  State<ClaimScreen> createState() => _ClaimScreenState();
}

class _ClaimScreenState extends State<ClaimScreen> {
  final _deviceId = TextEditingController();
  final _deviceSecret = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _submitting = false;
  String? _status;

  @override
  Widget build(BuildContext context) {
    final cfg = AppConfig.of(context)!;
    return SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Link a device to your account using its ID and secret.',
                    style: TextStyle(fontSize: 14, color: Color(0xFF475569)),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _deviceId,
                    decoration: const InputDecoration(labelText: 'Device ID'),
                    validator: (v) => (v == null || v.isEmpty) ? 'Device ID required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _deviceSecret,
                    decoration: const InputDecoration(labelText: 'Device secret'),
                    validator: (v) => (v == null || v.isEmpty) ? 'Secret required' : null,
                  ),
                  const SizedBox(height: 16),
                  if (_status != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        _status!,
                        style: TextStyle(
                          color: _status!.toLowerCase().contains('failed') ? Colors.red : Colors.green,
                        ),
                      ),
                    ),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _submitting
                          ? null
                          : () async {
                              if (!_formKey.currentState!.validate()) return;
                              setState(() {
                                _submitting = true;
                                _status = null;
                              });
                              try {
                                await ApiClient(cfg.baseUrl, cfg.token).claimDevice(
                                  _deviceId.text.trim(),
                                  _deviceSecret.text.trim(),
                                );
                                setState(() {
                                  _status = 'Device claimed!';
                                });
                              } catch (e) {
                                setState(() {
                                  _status = 'Claim failed: $e';
                                });
                              } finally {
                                setState(() {
                                  _submitting = false;
                                });
                              }
                            },
                      child: _submitting
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Claim device'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
    );
  }
}

class DeviceDetailScreen extends StatefulWidget {
  const DeviceDetailScreen({super.key, required this.deviceId, required this.name});

  final String deviceId;
  final String name;

  @override
  State<DeviceDetailScreen> createState() => _DeviceDetailScreenState();
}

class _DeviceDetailScreenState extends State<DeviceDetailScreen> {
  late Future<DeviceDetail> _future;
  late Future<List<DeviceAlert>> _alertsFuture;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final cfg = AppConfig.of(context)!;
    _future = ApiClient(cfg.baseUrl, cfg.token).fetchDeviceDetail(widget.deviceId);
    _alertsFuture = ApiClient(cfg.baseUrl, cfg.token).fetchDeviceAlerts(widget.deviceId);
  }

  void _refresh() {
    final cfg = AppConfig.of(context)!;
    setState(() {
      _future = ApiClient(cfg.baseUrl, cfg.token).fetchDeviceDetail(widget.deviceId);
      _alertsFuture = ApiClient(cfg.baseUrl, cfg.token).fetchDeviceAlerts(widget.deviceId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final cfg = AppConfig.of(context)!;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.name),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: FutureBuilder<DeviceDetail>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ErrorState(
              message: 'Could not load device',
              detail: snapshot.error.toString(),
              onRetry: _refresh,
            );
          }
          final detail = snapshot.data!;
          return RefreshIndicator(
            onRefresh: () async {
              _refresh();
              await _future;
            },
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Section(
                    title: 'Sensors',
                    child: Column(
                      children: detail.sensors
                          .map(
                            (s) => ListTile(
                              title: Text(s.type.replaceAll('_', ' ').toUpperCase()),
                              trailing: detail.latestReadings[s.id] != null
                                  ? Column(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: [
                                        Text(
                                          '${detail.latestReadings[s.id]!.value}${s.unit ?? ''}',
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                        ),
                                        Text(
                                          detail.latestReadings[s.id]!.timestamp,
                                          style: const TextStyle(fontSize: 10, color: Colors.grey),
                                        ),
                                      ],
                                    )
                                  : const Text('No data'),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                  _Section(
                    title: 'Manual Controls',
                    child: Column(
                      children: detail.actuators
                          .map(
                            (a) => _ActuatorControl(
                              actuator: a,
                              deviceId: widget.deviceId,
                              onCommandSent: _refresh,
                            ),
                          )
                          .toList(),
                    ),
                  ),
                  AutomationCard(detail: detail),
                  _AlertsSection(
                    deviceId: widget.deviceId,
                    alertsFuture: _alertsFuture,
                    onRefresh: _refresh,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ActuatorControl extends StatefulWidget {
  const _ActuatorControl({
    required this.actuator,
    required this.deviceId,
    required this.onCommandSent,
  });

  final ActuatorDto actuator;
  final String deviceId;
  final VoidCallback onCommandSent;

  @override
  State<_ActuatorControl> createState() => _ActuatorControlState();
}

class _ActuatorControlState extends State<_ActuatorControl> {
  bool _sending = false;

  Future<void> _sendCommand(String command) async {
    final cfg = AppConfig.of(context)!;
    setState(() => _sending = true);
    try {
      await ApiClient(cfg.baseUrl, cfg.token).sendCommand(
        widget.deviceId,
        widget.actuator.id,
        command,
      );
      widget.onCommandSent();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Command sent: $command')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to send command: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(widget.actuator.type.replaceAll('_', ' ').toUpperCase()),
      subtitle: Text('State: ${widget.actuator.state ?? "unknown"}'),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          ElevatedButton(
            onPressed: _sending ? null : () => _sendCommand('on'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF16a34a),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            ),
            child: const Text('ON'),
          ),
          const SizedBox(width: 8),
          OutlinedButton(
            onPressed: _sending ? null : () => _sendCommand('off'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            ),
            child: const Text('OFF'),
          ),
        ],
      ),
    );
  }
}

class _AlertsSection extends StatelessWidget {
  const _AlertsSection({
    required this.deviceId,
    required this.alertsFuture,
    required this.onRefresh,
  });

  final String deviceId;
  final Future<List<DeviceAlert>> alertsFuture;
  final VoidCallback onRefresh;

  Color _severityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return Colors.redAccent;
      case 'WARN':
        return Colors.orangeAccent;
      default:
        return Colors.blueGrey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Alerts',
      child: FutureBuilder<List<DeviceAlert>>(
        future: alertsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          if (snapshot.hasError) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Text('Could not load alerts: ${snapshot.error}'),
            );
          }
          final alerts = snapshot.data ?? [];
          if (alerts.isEmpty) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Text('No alerts for this device', style: TextStyle(color: Colors.grey)),
            );
          }
          return Column(
            children: alerts.map((alert) {
              return Card(
                margin: const EdgeInsets.symmetric(vertical: 4),
                color: _severityColor(alert.severity).withOpacity(0.1),
                child: ListTile(
                  title: Text(
                    alert.type.replaceAll('_', ' ').toUpperCase(),
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: _severityColor(alert.severity),
                    ),
                  ),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(alert.message),
                      if (alert.createdAt != null)
                        Text(
                          alert.createdAt!,
                          style: const TextStyle(fontSize: 11, color: Colors.grey),
                        ),
                    ],
                  ),
                  trailing: alert.resolvedAt != null
                      ? const Icon(Icons.check_circle, color: Colors.green)
                      : const Icon(Icons.warning, color: Colors.orange),
                ),
              );
            }).toList(),
          );
        },
      ),
    );
  }
}

class AutomationCard extends StatefulWidget {
  const AutomationCard({super.key, required this.detail});

  final DeviceDetail detail;

  @override
  State<AutomationCard> createState() => _AutomationCardState();
}

class _AutomationCardState extends State<AutomationCard> {
  late TextEditingController _soilMin;
  late TextEditingController _soilMax;
  late TextEditingController _tempMin;
  late TextEditingController _tempMax;
  late TextEditingController _waterMin;
  late TextEditingController _waterDuration;
  late TextEditingController _waterCooldown;
  late TextEditingController _lampOn;
  late TextEditingController _lampOff;
  bool _saving = false;
  String? _status;

  @override
  void initState() {
    super.initState();
    final p = widget.detail.automationProfile;
    _soilMin = TextEditingController(text: p?.soilMoistureMin?.toString());
    _soilMax = TextEditingController(text: p?.soilMoistureMax?.toString());
    _tempMin = TextEditingController(text: p?.tempMin?.toString());
    _tempMax = TextEditingController(text: p?.tempMax?.toString());
    _waterMin = TextEditingController(text: p?.minWaterLevel?.toString());
    _waterDuration =
        TextEditingController(text: p?.wateringDurationSec?.toString());
    _waterCooldown =
        TextEditingController(text: p?.wateringCooldownMin?.toString());
    _lampOn =
        TextEditingController(text: p?.lampSchedule?['on_minutes']?.toString());
    _lampOff = TextEditingController(
        text: p?.lampSchedule?['off_minutes']?.toString());
  }

  @override
  Widget build(BuildContext context) {
    final cfg = AppConfig.of(context)!;
    return _Section(
      title: 'Automation',
      child: Column(
        children: [
          _NumberField(label: 'Soil moisture min (%)', controller: _soilMin),
          _NumberField(label: 'Soil moisture max (%)', controller: _soilMax),
          _NumberField(label: 'Temp min (°C)', controller: _tempMin),
          _NumberField(label: 'Temp max (°C)', controller: _tempMax),
          _NumberField(label: 'Min water level (%)', controller: _waterMin),
          _NumberField(
              label: 'Watering duration (sec)', controller: _waterDuration),
          _NumberField(
              label: 'Watering cooldown (min)', controller: _waterCooldown),
          _NumberField(label: 'Lamp on minutes', controller: _lampOn),
          _NumberField(label: 'Lamp off minutes', controller: _lampOff),
          const SizedBox(height: 12),
          if (_status != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                _status!,
                style: const TextStyle(color: Colors.greenAccent),
              ),
            ),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _saving
                  ? null
                  : () async {
                      setState(() {
                        _saving = true;
                        _status = null;
                      });
                      final payload = <String, dynamic>{};
                      void put(TextEditingController c, String key) {
                        if (c.text.trim().isNotEmpty) {
                          payload[key] = double.tryParse(c.text.trim());
                        }
                      }

                      put(_soilMin, 'soil_moisture_min');
                      put(_soilMax, 'soil_moisture_max');
                      put(_tempMin, 'temp_min');
                      put(_tempMax, 'temp_max');
                      put(_waterMin, 'min_water_level');
                      put(_waterDuration, 'watering_duration_sec');
                      put(_waterCooldown, 'watering_cooldown_min');
                      final lamp = <String, dynamic>{};
                      if (_lampOn.text.trim().isNotEmpty) {
                        lamp['on_minutes'] = int.tryParse(_lampOn.text.trim());
                      }
                      if (_lampOff.text.trim().isNotEmpty) {
                        lamp['off_minutes'] =
                            int.tryParse(_lampOff.text.trim());
                      }
                      if (lamp.isNotEmpty) {
                        payload['lamp_schedule'] = lamp;
                      }

                      try {
                        await ApiClient(cfg.baseUrl, cfg.token)
                            .updateAutomation(widget.detail.id, payload);
                        setState(() {
                          _status = 'Saved';
                        });
                      } catch (e) {
                        setState(() {
                          _status = 'Save failed: $e';
                        });
                      } finally {
                        setState(() {
                          _saving = false;
                        });
                      }
                    },
              child: _saving
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save automation'),
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
        ),
        Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: child,
          ),
        ),
      ],
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({required this.label, required this.controller});
  final String label;
  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: TextField(
        controller: controller,
        keyboardType: TextInputType.number,
        decoration: InputDecoration(
          labelText: label,
          filled: true,
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.text, this.color});
  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = color ?? Colors.green;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: c.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        text,
        style: TextStyle(color: c),
      ),
    );
  }
}

// Helper function to format time difference
String _formatTimeSince(DateTime dateTime) {
  final now = DateTime.now().toUtc();
  final dt = dateTime.toUtc();
  final diff = now.difference(dt);

  if (diff.inSeconds < 60) {
    return '${diff.inSeconds}s ago';
  } else if (diff.inMinutes < 60) {
    return '${diff.inMinutes}m ago';
  } else if (diff.inHours < 24) {
    return '${diff.inHours}h ago';
  } else {
    return '${diff.inDays}d ago';
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.detail, this.onRetry});
  final String message;
  final String detail;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(message, style: const TextStyle(fontSize: 16)),
          const SizedBox(height: 4),
          Text(detail, style: const TextStyle(color: Colors.redAccent)),
          if (onRetry != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: ElevatedButton(
                onPressed: onRetry,
                child: const Text('Retry'),
              ),
            )
        ],
      ),
    );
  }
}

// --- Models & API client ---

class LoginResult {
  LoginResult({required this.token, required this.isAdmin});
  final String token;
  final bool isAdmin;
}

class Device {
  Device({
    required this.id,
    required this.name,
    this.model,
    required this.status,
    this.lastSeen,
  });

  final String id;
  final String name;
  final String? model;
  final String status;
  final String? lastSeen;

  static Device fromJson(Map<String, dynamic> json) {
    return Device(
      id: json['id'],
      name: json['name'],
      model: json['model'],
      status: json['status'],
      lastSeen: json['last_seen'],
    );
  }
}

class SensorDto {
  SensorDto({required this.id, required this.type, this.unit});
  final String id;
  final String type;
  final String? unit;

  static SensorDto fromJson(Map<String, dynamic> json) =>
      SensorDto(id: json['id'], type: json['type'], unit: json['unit']);
}

class ActuatorDto {
  ActuatorDto(
      {required this.id, required this.type, this.state, this.lastCommandAt});
  final String id;
  final String type;
  final String? state;
  final String? lastCommandAt;

  static ActuatorDto fromJson(Map<String, dynamic> json) => ActuatorDto(
        id: json['id'],
        type: json['type'],
        state: json['state'],
        lastCommandAt: json['last_command_at'],
      );
}

class AutomationProfileDto {
  AutomationProfileDto({
    this.soilMoistureMin,
    this.soilMoistureMax,
    this.tempMin,
    this.tempMax,
    this.minWaterLevel,
    this.wateringDurationSec,
    this.wateringCooldownMin,
    this.lampSchedule,
  });

  final double? soilMoistureMin;
  final double? soilMoistureMax;
  final double? tempMin;
  final double? tempMax;
  final double? minWaterLevel;
  final double? wateringDurationSec;
  final double? wateringCooldownMin;
  final Map<String, dynamic>? lampSchedule;

  static AutomationProfileDto? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    return AutomationProfileDto(
      soilMoistureMin: (json['soil_moisture_min'] as num?)?.toDouble(),
      soilMoistureMax: (json['soil_moisture_max'] as num?)?.toDouble(),
      tempMin: (json['temp_min'] as num?)?.toDouble(),
      tempMax: (json['temp_max'] as num?)?.toDouble(),
      minWaterLevel: (json['min_water_level'] as num?)?.toDouble(),
      wateringDurationSec: (json['watering_duration_sec'] as num?)?.toDouble(),
      wateringCooldownMin: (json['watering_cooldown_min'] as num?)?.toDouble(),
      lampSchedule: json['lamp_schedule'] as Map<String, dynamic>?,
    );
  }
}

class LatestReading {
  LatestReading(
      {required this.sensorId, required this.value, required this.timestamp});
  final String sensorId;
  final double value;
  final String timestamp;

  static LatestReading fromJson(Map<String, dynamic> json) => LatestReading(
        sensorId: json['sensor_id'],
        value: (json['value'] as num).toDouble(),
        timestamp: json['timestamp'],
      );
}

class DeviceDetail {
  DeviceDetail({
    required this.id,
    required this.sensors,
    required this.actuators,
    required this.latestReadings,
    this.automationProfile,
  });

  final String id;
  final List<SensorDto> sensors;
  final List<ActuatorDto> actuators;
  final Map<String, LatestReading> latestReadings;
  final AutomationProfileDto? automationProfile;
}

class DeviceAlert {
  DeviceAlert({
    required this.id,
    required this.deviceId,
    required this.type,
    required this.severity,
    required this.message,
    this.createdAt,
    this.resolvedAt,
  });

  final String id;
  final String deviceId;
  final String type;
  final String severity;
  final String message;
  final String? createdAt;
  final String? resolvedAt;

  static DeviceAlert fromJson(Map<String, dynamic> json) => DeviceAlert(
        id: json['id'],
        deviceId: json['device_id'],
        type: json['type'],
        severity: json['severity'],
        message: json['message'],
        createdAt: json['created_at'],
        resolvedAt: json['resolved_at'],
      );
}

class ApiClient {
  ApiClient(this.baseUrl, this.token);
  final String baseUrl;
  final String token;

  Map<String, String> get _headers {
    final headers = {'Content-Type': 'application/json'};
    if (token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  static Future<LoginResult> login(
      String baseUrl, String email, String password) async {
    final res = await http.post(
      Uri.parse('${baseUrl.trim()}/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (res.statusCode != 200) {
      throw Exception('HTTP ${res.statusCode}: ${res.body}');
    }
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final token = json['access_token'] as String?;
    final isAdmin = json['is_admin'] as bool? ?? false;
    if (token == null || token.isEmpty) {
      throw Exception('No access_token in response');
    }
    return LoginResult(token: token, isAdmin: isAdmin);
  }

  static Future<LoginResult> register(
      String baseUrl, String email, String password) async {
    final res = await http.post(
      Uri.parse('${baseUrl.trim()}/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw Exception('HTTP ${res.statusCode}: ${res.body}');
    }
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final token = json['access_token'] as String?;
    final isAdmin = json['is_admin'] as bool? ?? false;
    if (token == null || token.isEmpty) {
      throw Exception('No access_token in response');
    }
    return LoginResult(token: token, isAdmin: isAdmin);
  }

  Future<List<Device>> fetchDevices() async {
    final res = await http.get(Uri.parse('$baseUrl/devices'), headers: _headers);
    _ensureOk(res);
    final body = jsonDecode(res.body) as List;
    return body.map((e) => Device.fromJson(e)).toList();
  }

  Future<void> deleteDevice(String deviceId) async {
    final res = await http.delete(
      Uri.parse('$baseUrl/devices/$deviceId'),
      headers: _headers,
    );
    _ensureOk(res);
  }

  Future<void> claimDevice(String deviceId, String secret) async {
    final res = await http.post(
      Uri.parse('$baseUrl/devices/claim'),
      headers: _headers,
      body: jsonEncode({
        'device_id': deviceId,
        'device_secret': secret,
      }),
    );
    _ensureOk(res);
  }

  Future<DeviceDetail> fetchDeviceDetail(String deviceId) async {
    final deviceRes =
        await http.get(Uri.parse('$baseUrl/devices/$deviceId'), headers: _headers);
    _ensureOk(deviceRes);
    final deviceJson = jsonDecode(deviceRes.body) as Map<String, dynamic>;

    final latestRes = await http.get(
      Uri.parse('$baseUrl/telemetry/latest/$deviceId'),
      headers: _headers,
    );
    Map<String, LatestReading> latest = {};
    if (latestRes.statusCode == 200) {
      final latestJson = jsonDecode(latestRes.body) as Map<String, dynamic>;
      latest = {
        for (final r in (latestJson['readings'] as List<dynamic>))
          r['sensor_id'] as String: LatestReading.fromJson(
            Map<String, dynamic>.from(r as Map),
          )
      };
    }

    final sensors = (deviceJson['sensors'] as List)
        .map((e) => SensorDto.fromJson(Map<String, dynamic>.from(e)))
        .toList();
    final actuators = (deviceJson['actuators'] as List)
        .map((e) => ActuatorDto.fromJson(Map<String, dynamic>.from(e)))
        .toList();

    return DeviceDetail(
      id: deviceJson['id'],
      sensors: sensors,
      actuators: actuators,
      latestReadings: latest,
      automationProfile:
          AutomationProfileDto.fromJson(deviceJson['automation_profile']),
    );
  }

  Future<void> updateAutomation(
      String deviceId, Map<String, dynamic> payload) async {
    final res = await http.put(
      Uri.parse('$baseUrl/devices/$deviceId/automation'),
      headers: _headers,
      body: jsonEncode(payload),
    );
    _ensureOk(res);
  }

  Future<List<DeviceAlert>> fetchAlerts() async {
    final res = await http.get(Uri.parse('$baseUrl/alerts'), headers: _headers);
    _ensureOk(res);
    final body = jsonDecode(res.body) as List;
    return body
        .map((e) => DeviceAlert.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  Future<void> resolveAlert(String alertId) async {
    final res = await http.patch(
      Uri.parse('$baseUrl/alerts/$alertId/resolve'),
      headers: _headers,
    );
    _ensureOk(res);
  }

  Future<List<DeviceAlert>> fetchDeviceAlerts(String deviceId) async {
    final res = await http.get(
      Uri.parse('$baseUrl/alerts?device_id=$deviceId'),
      headers: _headers,
    );
    _ensureOk(res);
    final body = jsonDecode(res.body) as List;
    return body
        .map((e) => DeviceAlert.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  Future<void> sendCommand(String deviceId, String actuatorId, String command) async {
    final res = await http.post(
      Uri.parse('$baseUrl/commands/devices/$deviceId'),
      headers: _headers,
      body: jsonEncode({
        'actuator_id': actuatorId,
        'command': command,
      }),
    );
    _ensureOk(res);
  }

  void _ensureOk(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) return;
    throw Exception('HTTP ${res.statusCode}: ${res.body}');
  }
}
