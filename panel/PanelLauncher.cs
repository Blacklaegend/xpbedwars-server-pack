using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class PanelLauncher
{
    [STAThread]
    static void Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string panel = Path.Combine(dir, "panel", "ServerPanel.exe");
        if (!File.Exists(panel))
        {
            MessageBox.Show("找不到 panel\\ServerPanel.exe，请确认压缩包已完整解压。", "BedWars 服务器面板",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = panel;
            psi.WorkingDirectory = Path.Combine(dir, "panel");
            psi.UseShellExecute = true;
            Process.Start(psi);
        }
        catch (Exception ex)
        {
            MessageBox.Show("启动面板失败：\n" + ex.Message, "BedWars 服务器面板",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
