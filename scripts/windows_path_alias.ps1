function New-AsciiWorkspaceAlias {
    param([Parameter(Mandatory)][string]$Root)

    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    if ($resolvedRoot -notmatch '[^\x00-\x7F]') {
        return [pscustomobject]@{
            Root = $resolvedRoot
            Drive = $null
            Owned = $false
        }
    }

    $aliasRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'devcore-workspace'
    if (Test-Path -LiteralPath $aliasRoot) {
        $alias = Get-Item -LiteralPath $aliasRoot
        if ($alias.LinkType -ne 'Junction' -or $alias.Target -notcontains $resolvedRoot) {
            throw "O alias temporário já existe e aponta para outro local: $aliasRoot"
        }
    }
    else {
        New-Item -ItemType Junction -Path $aliasRoot -Target $resolvedRoot | Out-Null
    }

    return [pscustomobject]@{
        Root = $aliasRoot
        Drive = $null
        Owned = $false
    }
}

function Remove-AsciiWorkspaceAlias {
    param([Parameter(Mandatory)][object]$Alias)

    # A junção validada fica no diretório temporário para ser reutilizada por
    # Gradle/Flutter e nunca é removida enquanto um daemon ainda pode usá-la.
    $null = $Alias
}
