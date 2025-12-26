using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace MchoseConfigurator;

public partial class MonitorBar : UserControl
{
    public string Title { get => TitleText.Text; set => TitleText.Text = value; }
    public Brush BarColor { get => Bar.Foreground; set => Bar.Foreground = value; }
    public bool Centered { get; set; }

    public MonitorBar()
    {
        InitializeComponent();
    }

    public void Set(double value)
    {
        if (Centered)
        {
            // value esperado: -1..1 -> 0..1
            double v = (value + 1.0) / 2.0;
            Bar.Value = v;
            ValueText.Text = ((int)(value * 100)).ToString() + "%";
        }
        else
        {
            Bar.Value = value;
            ValueText.Text = ((int)(value * 100)).ToString() + "%";
        }
    }
}
