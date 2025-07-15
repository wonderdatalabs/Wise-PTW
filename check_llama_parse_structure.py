"""
Check the structure of the llama-cloud-services package.

Run this script to see the available modules, classes, and methods in the package.
"""

import importlib
import inspect
import sys

def check_package_structure(package_name):
    """Check the structure of a Python package."""
    try:
        # Try to import the package
        package = importlib.import_module(package_name)
        print(f"Successfully imported {package_name}")
        
        # Print package attributes
        print("\nPackage Attributes:")
        print("=" * 60)
        attributes = [attr for attr in dir(package) if not attr.startswith('_')]
        for attr in attributes:
            print(f"- {attr}")
        
        # Check for LlamaParse class
        if 'LlamaParse' in attributes:
            print("\nLlamaParse Class Structure:")
            print("=" * 60)
            llama_parse_class = getattr(package, 'LlamaParse')
            
            # Print methods
            methods = [method for method in dir(llama_parse_class) if not method.startswith('_')]
            print(f"Methods: {methods}")
            
            # Try to create an instance with empty API key to see the init parameters
            try:
                # This will likely fail, but we can catch the error to learn about the init params
                llama_parse = llama_parse_class()
            except TypeError as e:
                # Print the error message which should show the required parameters
                print(f"Constructor parameters: {str(e)}")
            
            # Try to get method signatures
            print("\nMethod Signatures:")
            for method in methods:
                try:
                    method_obj = getattr(llama_parse_class, method)
                    signature = inspect.signature(method_obj)
                    print(f"- {method}{signature}")
                except (ValueError, TypeError):
                    print(f"- {method}: Could not determine signature")
        
        # Check for submodules
        print("\nPossible Submodules:")
        print("=" * 60)
        
        for attr in attributes:
            try:
                submodule = importlib.import_module(f"{package_name}.{attr}")
                print(f"Submodule: {package_name}.{attr}")
                
                # Print submodule attributes
                submodule_attrs = [a for a in dir(submodule) if not a.startswith('_')]
                print(f"  Attributes: {submodule_attrs}")
            except (ImportError, AttributeError):
                continue
        
    except ImportError as e:
        print(f"Error importing {package_name}: {e}")
        return False
    
    except Exception as e:
        print(f"Error analyzing {package_name}: {e}")
        return False
    
    return True

if __name__ == "__main__":
    package_name = "llama_cloud_services"
    print(f"Checking structure of {package_name}...\n")
    
    success = check_package_structure(package_name)
    
    if not success:
        print(f"\nFailed to analyze {package_name}.")
        sys.exit(1)
    
    print(f"\nSuccessfully analyzed {package_name} structure.")