using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using HidSharp;
using Nefarius.ViGEm.Client;
using Nefarius.ViGEm.Client.Targets;
using Nefarius.ViGEm.Client.Targets.Xbox360;

namespace MchoseConfigurator;

public partial class MainWindow : Window
{
    private const int TargetVid = 0x41E4;
    private const int TargetPid = 0x211A;
    private const int ReportLen = 64;

    private readonly ObservableCollection<KeyViewModel> _keys = new();
    private readonly List<string> _actions = new()
    {
        "Gatillo Derecho (RT) - Acelerar",
        "Gatillo Izquierdo (LT) - Frenar",
        "Stick Izquierdo: DERECHA (X+)",
        "Stick Izquierdo: IZQUIERDA (X-)",
        "Stick Izquierdo: ARRIBA (Y+)",
        "Stick Izquierdo: ABAJO (Y-)",
        "Stick Derecho: DERECHA",
        "Stick Derecho: IZQUIERDA",
        "Stick Derecho: ARRIBA",
        "Stick Derecho: ABAJO",
        "Botón A",
        "Botón B",
        "Botón X",
        "Botón Y",
        "LB (Bumper Izq)",
        "RB (Bumper Der)",
        "Start",
        "Back"
    };

    private readonly Dictionary<byte, int> _active = new();
    private readonly object _stateLock = new();

    private Config _config;
    private readonly string _configPath;

    private ViGEmClient? _client;
    private IXbox360Controller? _pad;
    private HidStream? _stream;
    private CancellationTokenSource? _cts;
    private bool _connected;
    private string? _selectedKeyId;
    private bool _detectMode;
    private DateTime _lastAnalog = DateTime.MinValue;

    public MainWindow()
    {
        InitializeComponent();

        _configPath = ResolveConfigPath();
        _config = Config.Load(_configPath);

        BuildKeyboard();
        SetupUIFromConfig();

        ActionCombo.ItemsSource = _actions;
        KeyboardGrid.ItemsSource = _keys;
    }

    private void BuildKeyboard()
    {
        var layout = new[]
        {
            new (string label, string id)[] { ("Q", "20"), ("W", "26"), ("E", "8"), ("R", "21"), ("T", "23"), ("Y", "28"), ("U", "24"), ("I", "12"), ("O", "18"), ("P", "19") },
            new (string label, string id)[] { ("A", "4"), ("S", "22"), ("D", "7"), ("F", "9"), ("G", "10"), ("H", "11"), ("J", "13"), ("K", "14"), ("L", "15") },
            new (string label, string id)[] { ("Z", "29"), ("X", "27"), ("C", "6"), ("V", "25"), ("B", "5"), ("N", "17"), ("M", "16") },
            new (string label, string id)[] { ("Space", "44"), ("Ctrl", "224"), ("Shift", "225") }
        };

        foreach (var row in layout)
        {
            foreach (var key in row)
            {
                _keys.Add(new KeyViewModel { Id = key.id, Label = key.label });
            }
        }
    }

    private void SetupUIFromConfig()
    {
        DeadzoneSlider.Step = 1;
        DeadzoneSlider.Suffix = " u";
        DeadzoneSlider.Value = _config.Settings.Deadzone;
        DeadzoneSlider.ValueChanged += (_, v) =>
        {
            _config.Settings.Deadzone = (int)v;
            SaveConfig();
        };

        SensitivitySlider.Step = 0.05;
        SensitivitySlider.Suffix = "x";
        SensitivitySlider.Value = _config.Settings.Sensitivity;
        SensitivitySlider.ValueChanged += (_, v) =>
        {
            _config.Settings.Sensitivity = v;
            SaveConfig();
        };

        MaxPressureSlider.Step = 10;
        MaxPressureSlider.Suffix = " u";
        MaxPressureSlider.Value = _config.Settings.MaxPressure;
        MaxPressureSlider.ValueChanged += (_, v) =>
        {
            _config.Settings.MaxPressure = (int)v;
            SaveConfig();
        };

        AnalogOnlyCheck.IsChecked = false;
    }

    private async void ConnectButton_Click(object sender, RoutedEventArgs e)
    {
        if (_connected)
        {
            await DisconnectAsync();
            return;
        }

        StatusText.Text = "Conectando...";
        ConnectButton.IsEnabled = false;

        try
        {
            await Task.Run(() => Connect());
            _connected = true;
            StatusText.Text = "Conectado";
            StatusText.Foreground = System.Windows.Media.Brushes.LightGreen;
            ConnectButton.Content = "Desconectar";
            ModeText.Text = string.Empty;
        }
        catch (Exception ex)
        {
            StatusText.Text = "Error de conexión";
            StatusText.Foreground = System.Windows.Media.Brushes.OrangeRed;
            MessageBox.Show(ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            await DisconnectAsync();
        }
        finally
        {
            ConnectButton.IsEnabled = true;
        }
    }

    private void Connect()
    {
        _client = new ViGEmClient();
        _pad = _client.CreateXbox360Controller();
        _pad.Connect();

        // Find device - prioritize MI_01 (interface 1) which has analog data
        var list = DeviceList.Local.GetHidDevices(TargetVid, TargetPid).ToList();
        
        // Sort: MI_01 first, then others
        var sorted = list.OrderBy(d => 
        {
            var p = d.DevicePath?.ToLower() ?? "";
            if (p.Contains("mi_01")) return 0;
            return 1;
        }).ToList();

        HidDevice? device = null;
        foreach (var dev in sorted)
        {
            try
            {
                var cfg = new OpenConfiguration();
                cfg.SetOption(OpenOption.Exclusive, false);
                _stream = dev.Open(cfg);
                _stream.ReadTimeout = Timeout.Infinite;
                device = dev;
                break;
            }
            catch { }
        }

        if (_stream == null)
        {
            throw new InvalidOperationException("No se pudo abrir el teclado Mchose");
        }

        _cts = new CancellationTokenSource();
        Task.Run(() => ReadLoop(_cts.Token));
    }

    private async Task DisconnectAsync()
    {
        _cts?.Cancel();
        _cts = null;

        await Task.Delay(50);

        _stream?.Dispose();
        _stream = null;

        _pad?.Disconnect();
        _pad = null;

        _client?.Dispose();
        _client = null;

        lock (_stateLock)
        {
            _active.Clear();
        }

        _detectMode = false;

        foreach (var k in _keys)
        {
            k.IsActive = false;
        }

        _connected = false;
        ConnectButton.Content = "🔌 Conectar";
        StatusText.Text = "Desconectado";
        StatusText.Foreground = System.Windows.Media.Brushes.OrangeRed;
        ModeText.Text = string.Empty;
    }

    private void ReadLoop(CancellationToken ct)
    {
        if (_stream == null || _pad == null) return;
        var buffer = new byte[ReportLen];

        while (!ct.IsCancellationRequested)
        {
            int read;
            try
            {
                read = _stream.Read(buffer, 0, ReportLen);
            }
            catch
            {
                Dispatcher.Invoke(async () => await DisconnectAsync());
                break;
            }

            if (read == 0) continue;

            // Parse EXACTLY like Python: data[0] == 0xA0, key = data[3], raw = (data[4] << 8) | data[5]
            if (read > 6 && buffer[0] == 0xA0)
            {
                byte key = buffer[3];
                int raw = (buffer[4] << 8) | buffer[5];

                _lastAnalog = DateTime.UtcNow;
                
                // Apply deadzone IMMEDIATELY - only consider key active if above deadzone
                int deadzone = _config.Settings.Deadzone;
                
                lock (_stateLock)
                {
                    if (raw > deadzone)
                    {
                        _active[key] = raw;
                    }
                    else
                    {
                        _active.Remove(key);
                    }
                }

                if (_detectMode && raw > deadzone)
                {
                    _detectMode = false;
                    Dispatcher.Invoke(() => ShowDetectedKey(key, raw));
                }

                // Only show debug for meaningful presses
                if (raw > deadzone)
                {
                    Dispatcher.Invoke(() => DebugText.Text = $"Key=0x{key:X2} raw={raw} active={_active.Count}");
                }

                // Process mapping on every analog packet
                Dictionary<byte, int> snapshot;
                lock (_stateLock)
                {
                    snapshot = new Dictionary<byte, int>(_active);
                }
                ProcessMapping(snapshot);
                Dispatcher.Invoke(() => UpdateKeyHighlights(snapshot));
            }
        }
    }

    private void ProcessMapping(Dictionary<byte, int> active)
    {
        if (_pad == null) return;

        short lx = 0, ly = 0, rx = 0, ry = 0;
        byte lt = 0, rt = 0;
        var pressed = new HashSet<Xbox360Button>();

        foreach (var kv in active)
        {
            string key = kv.Key.ToString();
            if (!_config.Mappings.TryGetValue(key, out var action)) continue;
            int raw = kv.Value;
            int val = ProcessAnalog(raw, _config.Settings);
            byte trig = (byte)Math.Clamp((val * 255) / 32767, 0, 255);
            short axis = (short)Math.Clamp(val, 0, 32767);

            switch (action)
            {
                case "Gatillo Derecho (RT) - Acelerar": rt = Math.Max(rt, trig); break;
                case "Gatillo Izquierdo (LT) - Frenar": lt = Math.Max(lt, trig); break;
                case "Stick Izquierdo: DERECHA (X+)": lx = (short)Math.Clamp(lx + axis, short.MinValue, short.MaxValue); break;
                case "Stick Izquierdo: IZQUIERDA (X-)": lx = (short)Math.Clamp(lx - axis, short.MinValue, short.MaxValue); break;
                case "Stick Izquierdo: ARRIBA (Y+)": ly = (short)Math.Clamp(ly + axis, short.MinValue, short.MaxValue); break;
                case "Stick Izquierdo: ABAJO (Y-)": ly = (short)Math.Clamp(ly - axis, short.MinValue, short.MaxValue); break;
                case "Stick Derecho: DERECHA": rx = (short)Math.Clamp(rx + axis, short.MinValue, short.MaxValue); break;
                case "Stick Derecho: IZQUIERDA": rx = (short)Math.Clamp(rx - axis, short.MinValue, short.MaxValue); break;
                case "Stick Derecho: ARRIBA": ry = (short)Math.Clamp(ry + axis, short.MinValue, short.MaxValue); break;
                case "Stick Derecho: ABAJO": ry = (short)Math.Clamp(ry - axis, short.MinValue, short.MaxValue); break;
                case "Botón A": if (trig > 100) pressed.Add(Xbox360Button.A); break;
                case "Botón B": if (trig > 100) pressed.Add(Xbox360Button.B); break;
                case "Botón X": if (trig > 100) pressed.Add(Xbox360Button.X); break;
                case "Botón Y": if (trig > 100) pressed.Add(Xbox360Button.Y); break;
                case "LB (Bumper Izq)": if (trig > 100) pressed.Add(Xbox360Button.LeftShoulder); break;
                case "RB (Bumper Der)": if (trig > 100) pressed.Add(Xbox360Button.RightShoulder); break;
                case "Start": if (trig > 100) pressed.Add(Xbox360Button.Start); break;
                case "Back": if (trig > 100) pressed.Add(Xbox360Button.Back); break;
            }
        }

        _pad.SetSliderValue(Xbox360Slider.LeftTrigger, lt);
        _pad.SetSliderValue(Xbox360Slider.RightTrigger, rt);
        _pad.SetAxisValue(Xbox360Axis.LeftThumbX, lx);
        _pad.SetAxisValue(Xbox360Axis.LeftThumbY, ly);
        _pad.SetAxisValue(Xbox360Axis.RightThumbX, rx);
        _pad.SetAxisValue(Xbox360Axis.RightThumbY, ry);

        _pad.SetButtonState(Xbox360Button.A, pressed.Contains(Xbox360Button.A));
        _pad.SetButtonState(Xbox360Button.B, pressed.Contains(Xbox360Button.B));
        _pad.SetButtonState(Xbox360Button.X, pressed.Contains(Xbox360Button.X));
        _pad.SetButtonState(Xbox360Button.Y, pressed.Contains(Xbox360Button.Y));
        _pad.SetButtonState(Xbox360Button.LeftShoulder, pressed.Contains(Xbox360Button.LeftShoulder));
        _pad.SetButtonState(Xbox360Button.RightShoulder, pressed.Contains(Xbox360Button.RightShoulder));
        _pad.SetButtonState(Xbox360Button.Start, pressed.Contains(Xbox360Button.Start));
        _pad.SetButtonState(Xbox360Button.Back, pressed.Contains(Xbox360Button.Back));

        _pad.SubmitReport();

        double lxNorm = Math.Clamp(lx / 32767.0, -1.0, 1.0);
        double lyNorm = Math.Clamp(ly / 32767.0, -1.0, 1.0);
        double rtNorm = rt / 255.0;
        double ltNorm = lt / 255.0;

        Dispatcher.Invoke(() =>
        {
            RtBar.Set(rtNorm);
            LtBar.Set(ltNorm);
            LxBar.Set(lxNorm);
            LyBar.Set(lyNorm);
        });
    }

    private void UpdateKeyHighlights(Dictionary<byte, int> active)
    {
        foreach (var key in _keys)
        {
            key.IsActive = active.ContainsKey(byte.Parse(key.Id));
        }
    }

    private static int ProcessAnalog(int raw, Settings s)
    {
        if (!s.AnalogMode) return raw > s.Deadzone ? 32767 : 0;
        if (raw <= s.Deadzone) return 0;
        double norm = Math.Min(1.0, (raw - s.Deadzone) / (double)(s.MaxPressure - s.Deadzone));
        if (s.Curve == "aggressive") norm = Math.Sqrt(norm);
        else if (s.Curve == "smooth") norm = norm * norm;
        norm *= s.Sensitivity;
        int val = (int)(norm * 32767);
        return Math.Clamp(val, 0, 32767);
    }

    private void KeyboardKey_MouseLeftButtonUp(object sender, System.Windows.Input.MouseButtonEventArgs e)
    {
        if (sender is KeyboardKey kk && kk.DataContext is KeyViewModel vm)
        {
            SelectKey(vm);
        }
    }

    private void SelectKey(KeyViewModel vm)
    {
        foreach (var key in _keys)
        {
            key.IsSelected = key == vm;
        }
        _selectedKeyId = vm.Id;
        SelectedKeyText.Text = $"Key {vm.Label} (id {vm.Id})";
        ActionCombo.IsEnabled = true;

        if (_config.Mappings.TryGetValue(vm.Id, out var existing))
        {
            ActionCombo.SelectedItem = existing;
        }
        else
        {
            ActionCombo.SelectedItem = null;
        }
    }

    private void ActionCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_selectedKeyId == null) return;
        if (ActionCombo.SelectedItem is string action)
        {
            _config.Mappings[_selectedKeyId] = action;
            SaveConfig();
        }
    }

    private void SaveMapping_Click(object sender, RoutedEventArgs e)
    {
        SaveConfig();
    }

    private void ClearMappings_Click(object sender, RoutedEventArgs e)
    {
        _config.Mappings.Clear();
        SaveConfig();
        ActionCombo.SelectedItem = null;
        SelectedKeyText.Text = "Mapeos borrados";
    }

    private void DetectRaw_Click(object sender, RoutedEventArgs e)
    {
        _detectMode = true;
        ModeText.Text = "Modo detección: presiona una tecla";
        DebugText.Text = string.Empty;
    }

    private void ShowDetectedKey(byte key, int raw)
    {
        ModeText.Text = $"Detectado key 0x{key:X2} raw={raw}";
        var found = _keys.FirstOrDefault(k => k.Id == key.ToString());
        if (found != null)
        {
            SelectKey(found);
        }
        else
        {
            SelectedKeyText.Text = $"Key 0x{key:X2} (sin visual)";
            ActionCombo.IsEnabled = true;
        }
    }

    private void SaveConfig()
    {
        var options = new JsonSerializerOptions { WriteIndented = true };
        var json = JsonSerializer.Serialize(_config, options);
        File.WriteAllText(_configPath, json);
    }

    private void AnalogOnlyCheck_Checked(object sender, RoutedEventArgs e)
    {
        // This toggle is no longer needed - we always use analog only with HidApi
        ModeText.Text = "Solo analógico";
    }

    private static string ResolveConfigPath()
    {
        var candidates = new List<string>
        {
            Path.Combine(Environment.CurrentDirectory, "mchose_config.json"),
            Path.Combine(AppContext.BaseDirectory, "mchose_config.json"),
            Path.Combine(AppContext.BaseDirectory, "..", "mchose_config.json"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "mchose_config.json"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "mchose_config.json"),
            Path.Combine("d:\\Code", "mchose_config.json")
        };

        foreach (var path in candidates)
        {
            try
            {
                var full = Path.GetFullPath(path);
                if (File.Exists(full)) return full;
            }
            catch { }
        }

        return candidates.First();
    }

    protected override async void OnClosing(CancelEventArgs e)
    {
        await DisconnectAsync();
        base.OnClosing(e);
    }
}

public class KeyViewModel : INotifyPropertyChanged
{
    private bool _isActive;
    private bool _isSelected;

    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;

    public bool IsActive
    {
        get => _isActive;
        set
        {
            if (_isActive == value) return;
            _isActive = value;
            OnPropertyChanged(nameof(IsActive));
        }
    }

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected == value) return;
            _isSelected = value;
            OnPropertyChanged(nameof(IsSelected));
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnPropertyChanged(string name) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

public class Config
{
    public Dictionary<string, string> Mappings { get; set; } = new();
    public Settings Settings { get; set; } = new();

    public static Config Load(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                var json = File.ReadAllText(path);
                return JsonSerializer.Deserialize<Config>(json) ?? new Config();
            }
        }
        catch
        {
            // ignore and return defaults
        }
        return new Config();
    }
}

public class Settings
{
    public int Deadzone { get; set; } = 30;
    public double Sensitivity { get; set; } = 1.0;
    public int MaxPressure { get; set; } = 600;
    public bool AnalogMode { get; set; } = true;
    public string Curve { get; set; } = "linear";
}
