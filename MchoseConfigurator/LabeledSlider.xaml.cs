using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace MchoseConfigurator;

public partial class LabeledSlider : UserControl
{
    public static readonly DependencyProperty TitleProperty = DependencyProperty.Register(
        nameof(Title), typeof(string), typeof(LabeledSlider), new PropertyMetadata(string.Empty, OnTitleChanged));

    public static readonly DependencyProperty ValueProperty = DependencyProperty.Register(
        nameof(Value), typeof(double), typeof(LabeledSlider), new PropertyMetadata(0d, OnValueChanged));

    public static readonly DependencyProperty MinimumProperty = DependencyProperty.Register(
        nameof(Minimum), typeof(double), typeof(LabeledSlider), new PropertyMetadata(0d, OnMinimumChanged));

    public static readonly DependencyProperty MaximumProperty = DependencyProperty.Register(
        nameof(Maximum), typeof(double), typeof(LabeledSlider), new PropertyMetadata(1d, OnMaximumChanged));

    public static readonly DependencyProperty StepProperty = DependencyProperty.Register(
        nameof(Step), typeof(double), typeof(LabeledSlider), new PropertyMetadata(0.01d));

    public static readonly DependencyProperty SuffixProperty = DependencyProperty.Register(
        nameof(Suffix), typeof(string), typeof(LabeledSlider), new PropertyMetadata(string.Empty));

    public string Title
    {
        get => (string)GetValue(TitleProperty);
        set => SetValue(TitleProperty, value);
    }

    public double Value
    {
        get => (double)GetValue(ValueProperty);
        set => SetValue(ValueProperty, value);
    }

    public double Minimum
    {
        get => (double)GetValue(MinimumProperty);
        set => SetValue(MinimumProperty, value);
    }

    public double Maximum
    {
        get => (double)GetValue(MaximumProperty);
        set => SetValue(MaximumProperty, value);
    }

    public double Step
    {
        get => (double)GetValue(StepProperty);
        set => SetValue(StepProperty, value);
    }

    public string Suffix
    {
        get => (string)GetValue(SuffixProperty);
        set => SetValue(SuffixProperty, value);
    }

    public event EventHandler<double>? ValueChanged;

    public LabeledSlider()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        TitleText.Text = Title;
        Slider.Minimum = Minimum;
        Slider.Maximum = Maximum;
        Slider.Value = Value;
        UpdateValueText();
    }

    private static void OnTitleChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (LabeledSlider)d;
        control.TitleText.Text = e.NewValue as string ?? string.Empty;
    }

    private static void OnValueChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (LabeledSlider)d;
        var newValue = (double)e.NewValue;
        if (Math.Abs(control.Slider.Value - newValue) > double.Epsilon)
        {
            control.Slider.Value = newValue;
        }
        control.UpdateValueText();
    }

    private static void OnMinimumChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (LabeledSlider)d;
        control.Slider.Minimum = (double)e.NewValue;
    }

    private static void OnMaximumChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var control = (LabeledSlider)d;
        control.Slider.Maximum = (double)e.NewValue;
    }

    private void Slider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (Step > 0)
        {
            var snapped = Math.Round(e.NewValue / Step) * Step;
            if (Math.Abs(snapped - Slider.Value) > double.Epsilon)
            {
                Slider.Value = snapped;
                return;
            }
        }

        if (Math.Abs(Value - e.NewValue) > double.Epsilon)
        {
            Value = e.NewValue;
            ValueChanged?.Invoke(this, Value);
        }
        UpdateValueText();
    }

    private void UpdateValueText()
    {
        ValueText.Text = string.Concat(Value.ToString("0.###", CultureInfo.InvariantCulture), Suffix);
    }

    protected override void OnMouseWheel(MouseWheelEventArgs e)
    {
        base.OnMouseWheel(e);
        var delta = e.Delta > 0 ? Step : -Step;
        var next = Math.Min(Maximum, Math.Max(Minimum, Slider.Value + delta));
        Slider.Value = next;
    }
}
