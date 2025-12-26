using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace MchoseConfigurator;

public partial class KeyboardKey : UserControl
{
    public static readonly DependencyProperty KeyIdProperty = DependencyProperty.Register(
        nameof(KeyId), typeof(string), typeof(KeyboardKey), new PropertyMetadata(string.Empty));

    public static readonly DependencyProperty DisplayProperty = DependencyProperty.Register(
        nameof(Display), typeof(string), typeof(KeyboardKey), new PropertyMetadata(string.Empty, OnDisplayChanged));

    public static readonly DependencyProperty IsActiveProperty = DependencyProperty.Register(
        nameof(IsActive), typeof(bool), typeof(KeyboardKey), new PropertyMetadata(false, OnIsActiveChanged));

    public static readonly DependencyProperty IsSelectedProperty = DependencyProperty.Register(
        nameof(IsSelected), typeof(bool), typeof(KeyboardKey), new PropertyMetadata(false, OnIsSelectedChanged));

    private readonly SolidColorBrush _selectedBrush = new SolidColorBrush(Color.FromRgb(88, 166, 255));
    private readonly SolidColorBrush _activeBrush = new SolidColorBrush(Color.FromRgb(46, 160, 67));

    public string KeyId
    {
        get => (string)GetValue(KeyIdProperty);
        set => SetValue(KeyIdProperty, value);
    }

    public string Display
    {
        get => (string)GetValue(DisplayProperty);
        set => SetValue(DisplayProperty, value);
    }

    public bool IsActive
    {
        get => (bool)GetValue(IsActiveProperty);
        set => SetValue(IsActiveProperty, value);
    }

    public bool IsSelected
    {
        get => (bool)GetValue(IsSelectedProperty);
        set => SetValue(IsSelectedProperty, value);
    }

    public KeyboardKey()
    {
        InitializeComponent();
        Label.Text = Display;
    }

    private static void OnDisplayChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (KeyboardKey)d;
        control.Label.Text = e.NewValue as string ?? string.Empty;
    }

    private static void OnIsActiveChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (KeyboardKey)d;
        control.Highlight.Fill = control._activeBrush;
        control.Highlight.Opacity = (bool)e.NewValue ? 0.35 : 0;
    }

    private static void OnIsSelectedChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (KeyboardKey)d;
        control.Border.BorderBrush = (bool)e.NewValue ? control._selectedBrush : new SolidColorBrush(Color.FromRgb(48, 54, 61));
    }
}
