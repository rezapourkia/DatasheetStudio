// XmlCapture — DipTrace CompEdit plug-in that captures the exchange XML
// produced by DipTrace so the real 5.x component-library serialization can
// be studied (ground truth for docs/diptrace conventions).
//
// DipTrace launches the plug-in executable with the exchange XML path as
// argv[1] (args[0] in .NET). With ImpMode=None DipTrace does not read the
// file back, so we only COPY it — never modify the original.
//
// Build (no extra tools required; ships with Windows .NET Framework):
//   csc.exe /nologo /target:exe /out:XmlCapture.exe XmlCapture.cs
using System;
using System.IO;

class XmlCapture
{
    static int Main(string[] args)
    {
        string dest = @"C:\Users\Pardis\DatasheetStudio\docs\diptrace\captures\plugin_capture.xml";
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            if (args.Length > 0 && File.Exists(args[0]))
            {
                File.Copy(args[0], dest, true);
                File.WriteAllText(dest + ".src", args[0]);
                return 0;
            }
            File.WriteAllText(dest + ".error", "no input XML argument");
            return 1;
        }
        catch (Exception ex)
        {
            try { File.WriteAllText(dest + ".error", ex.ToString()); }
            catch { /* never crash the host */ }
            return 1;
        }
    }
}
