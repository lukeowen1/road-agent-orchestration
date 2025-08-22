"""
run_all_tests.py - Run all unit tests and generate coverage report
"""
import unittest
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


def run_all_tests():
    """Discover and run all tests"""
    # Create test loader
    loader = unittest.TestLoader()
    
    # Discover all test files
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Create runner with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests
    print("=" * 70)
    print("RUNNING ALL UNIT TESTS")
    print("=" * 70)
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        
        if result.failures:
            print("\nFailed tests:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        
        if result.errors:
            print("\nTests with errors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
        
        return 1


def run_with_coverage():
    """Run tests with coverage report"""
    try:
        import coverage
    except ImportError:
        print("Coverage not installed. Install with: pip install coverage")
        return run_all_tests()
    
    # Start coverage
    cov = coverage.Coverage(source=['.'], omit=['test_*.py', 'run_all_tests.py'])
    cov.start()
    
    # Run tests
    exit_code = run_all_tests()
    
    # Stop coverage
    cov.stop()
    cov.save()
    
    # Print coverage report
    print("\n" + "=" * 70)
    print("COVERAGE REPORT")
    print("=" * 70)
    cov.report()
    
    # Generate HTML report
    print("\nGenerating HTML coverage report...")
    cov.html_report(directory='htmlcov')
    print("HTML report saved to: htmlcov/index.html")
    
    return exit_code


def run_specific_test_file(test_file):
    """Run a specific test file"""
    print(f"Running tests from: {test_file}")
    print("=" * 70)
    
    # Load the specific test module
    loader = unittest.TestLoader()
    
    try:
        # Remove .py extension if present
        if test_file.endswith('.py'):
            test_file = test_file[:-3]
        
        # Load tests from module
        suite = loader.loadTestsFromName(test_file)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return 0 if result.wasSuccessful() else 1
    except Exception as e:
        print(f"Error occurred while running tests: {e}")
        return 1

if __name__ == "__main__":
    run_all_tests()