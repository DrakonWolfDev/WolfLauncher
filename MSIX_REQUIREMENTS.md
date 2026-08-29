# MSIX Packaging Requirements for WolfLauncher

## Overview
This document outlines what would be required to package WolfLauncher as an MSIX application for Windows distribution, either through Microsoft Store or sideloading.

## Key Challenges for WolfLauncher MSIX Packaging

1. **File System Access**: WolfLauncher needs to access:
   - Steam installations (typically in `C:\Program Files (x86)\Steam` or custom locations)
   - Steam Workshop folders (`...\steamapps\workshop\content\221100\`)
   - User AppData folders for configuration and cache
   - Potentially launch DayZ and Steam executables

2. **Process Launching**: Need to launch:
   - `steam.exe` with `-applaunch 221100` parameters
   - Potentially `DayZ_x64.exe` or `DayZ_BE.exe`

3. **Registry Access**: Reading Steam installation paths from Windows Registry

## Required MSIX Capabilities

Based on the functionality needed, WolfLauncher would likely require these capabilities in its `Package.appxmanifest`:

### Standard Capabilities (automatically approved):
- `internetClient` - For WolfAPI server discovery, status checks
- `privateNetworkClientServer` - For local network server discovery

### Restricted Capabilities (require special justification):
- `broadFileSystemAccess` - **CRITICAL** - Needed to access arbitrary Steam/Workshop locations
  - Requires special approval from Microsoft for Store distribution
  - Allows access to all files user can access
- `executionAlias` - May be needed for launching external processes

### Possibly Needed:
- `registry` - For reading Steam registry keys (though file system access might suffice)

## MSIX Package Structure

```
WolfLauncher/
├── AppXManifest.xml          # Package manifest
├── WolfLauncher.exe          # Main executable (from PyInstaller)
├── runtime/                  # Bundled Python runtime
│   ├── python.exe
│   ├── DLLs
│   └── Lib/
├── node/                     # Bundled Node.js for gamedig
│   ├── node.exe
│   └── node_modules/
│       └── gamedig/
├── assets/                   # Application assets
│   ├── wolflauncher.ico
│   └── StoreLogo*.png
└── wolfgluauncher/           # Python application code
    ├── __init__.py
    ├── main.py
    └── (rest of wolflauncher package)
```

## Required Modifications to Build Process

1. **PyInstaller Adaptation**:
   - Modify `.spec` file to collect files into MSIX layout
   - Ensure all data files are properly included

2. **Manifest Generation**:
   - Create `AppXManifest.xml` with proper identity, capabilities, dependencies
   - Include visual assets for different scale factors

3. **Signing**:
   - Obtain code-signing certificate from trusted CA
   - Sign the MSIX package with `SignTool`
   - For Store distribution: Microsoft handles re-signing with their certificate

4. **Dependencies Handling**:
   - Option 1: Bundle Python runtime and Node.js (increases package size)
   - Option 2: Use MSIX Framework packages for Python/Node.js (requires ensuring availability)
   - Option 3: Prerequisite check and download (more complex)

## Sample AppXManifest.xml Outline

```xml
<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:mp="http://schemas.microsoft.com/appx/2014/manifest"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:desktop2="http://schemas.microsoft.com/appx/manifest/desktop/windows10"
  IgnorableNamespaces="uap mp desktop2">

  <Identity
    Name="WolfLauncher"
    Publisher="CN=Andrew Hodgson trading as Wolf Forge"
    Version="0.9.0.0" />

  <Properties>
    <DisplayName>WolfLauncher</DisplayName>
    <PublisherDisplayName>Andrew Hodgson trading as Wolf Forge</PublisherDisplayName>
    <Logo>assets\StoreLogo.png</Logo>
  </Properties>

  <Resources>
    <Resource Language="en-us" />
  </Resources>

  <Dependencies>
    <!-- Optional: Depend on framework packages if not bundling -->
    <!-- <Dependency Name="Microsoft.VCLibs.140.00" MinVersion="14.0.27323.0" /> -->
  </Dependencies>

  <Capabilities>
    <Capability Name="internetClient" />
    <Capability Name="privateNetworkClientServer" />
    <!-- REQUIRED for Steam/Workshop access -->
    <Capability Name="broadFileSystemAccess" />
  </Capabilities>

  <Applications>
    <Application
      Id="WolfLauncher"
      Executable="WolfLauncher.exe"
      EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="WolfLauncher"
        Square150x150Logo="assets\StoreLogo.png"
        Square44x44Logo="assets\StoreLogo.png"
        Description="DayZ launcher that validates modded servers before launch"
        BackgroundColor="#464646">
        <uap:DefaultTile Wide310x150Logo="assets\StoreWideLogo.png" />
        <uap:SplashScreen Image="assets\StoreSplash.png" />
      </uap:VisualElements>
      
      <!-- File Type Associations if needed -->
      <Extensions>
        <Extension Category="windows.fileTypeAssociation">
          <FileTypeAssociation Name="wolfserver">
            <SupportedFileTypes>
              <FileType>.wolfserver</FileType>
            </SupportedFileTypes>
          </FileTypeAssociation>
        </Extension>
      </Extensions>
    </Application>
  </Applications>
</Package>
```

## Build & Packaging Steps

1. Build WolfLauncher.exe using PyInstaller (current process)
2. Organize output into MSIX layout
3. Create AppXManifest.xml
4. Generate necessary image assets
5. Package using `MakeAppx.exe`
6. Sign using `SignTool.exe` with Authenticode certificate
7. For Store: Submit to Microsoft Partner Center

## Distribution Options

### A. Microsoft Store
- Pros: Automatic updates, no SmartScreen warnings, easy discovery
- Cons: 
  - Requires `broadFileSystemAccess` approval (not guaranteed)
  - Store review process
  - 15% revenue cut (if monetized)
  - Less control over update timing
  - Possible restrictions on certain launcher functionalities

### B. Sideloaded MSIX (Enterprise/Business)
- Pros: 
  - Same reliability/update benefits as Store
  - No Store review
  - Direct distribution control
- Cons:
  - Requires trusting the certificate or enabling sideloading
  - No automatic Store discovery
  - Still need code-signing certificate

### C. Hybrid Approach
- Keep current EXE/MSI for advanced users
- Offer MSIX through Store for casual users
- Maintain both distribution channels

## Recommendation

Given that WolfLauncher requires deep system integration (accessing arbitrary Steam locations, launching games), the `broadFileSystemAccess` capability is likely essential. This creates a significant hurdle for Microsoft Store distribution since:

1. Microsoft scrutinizes `broadFileSystemAccess` requests heavily
2. They may deny it if they believe the functionality can be achieved through more restricted means
3. Even if approved, there may be usage restrictions

**Alternative Path**: Continue with the planned signed EXE/MSI approach (UPDATE_STRATEGY.md) but:
1. Implement proper Authenticode signing
2. Consider using MSIX only as an update mechanism (not primary install)
3. Evaluate if limited file system access (known Steam locations only) could reduce capability needs

## Next Steps if Pursuing MSIX

1. Prototype MSIX packaging with broadFileSystemAccess
2. Test functionality limitations due to containerization
3. Evaluate if Store approval is feasible
4. Compare user experience vs. signed traditional installer